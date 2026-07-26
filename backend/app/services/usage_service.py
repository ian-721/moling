from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import Settings
from app.db_models import GlobalBudgetWindow, Principal, UsageWindow
from app.providers.base import TokenUsage

FLASH_INPUT_CNY_PER_MILLION = 1.0
FLASH_CACHE_CNY_PER_MILLION = 0.02
FLASH_OUTPUT_CNY_PER_MILLION = 2.0
PRO_INPUT_CNY_PER_MILLION = 3.0
PRO_CACHE_CNY_PER_MILLION = 0.025
PRO_OUTPUT_CNY_PER_MILLION = 6.0


class UsageGateError(RuntimeError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class UsageSnapshot:
    daily_used: int
    monthly_used: int


def _window_start(now: datetime, kind: str) -> datetime:
    if kind == "minute":
        return now.replace(second=0, microsecond=0)
    if kind == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"unsupported window kind: {kind}")


def _usage_window(
    session: Session, principal_id: str, kind: str, now: datetime
) -> UsageWindow:
    start = _window_start(now, kind)
    window = (
        session.query(UsageWindow)
        .filter_by(
            principal_id=principal_id,
            window_kind=kind,
            window_start=start,
        )
        .with_for_update()
        .one_or_none()
    )
    if window is None:
        window = UsageWindow(
            principal_id=principal_id,
            window_kind=kind,
            window_start=start,
        )
        session.add(window)
        session.flush()
    return window


class UsageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.reservation = Decimal(str(settings.request_cost_reservation_cny))

    def reserve(self, session: Session, principal_id: str) -> None:
        now = datetime.now(timezone.utc)
        # Locking the principal serializes all quota reservations for this
        # identity across workers and application instances.
        principal = session.get(Principal, principal_id, with_for_update=True)
        if principal is None or principal.status != "active":
            raise UsageGateError("invalid_principal", 401)

        minute = _usage_window(session, principal_id, "minute", now)
        if minute.request_count >= self.settings.principal_requests_per_minute:
            raise UsageGateError("rate_limit_exceeded", 429)
        minute.request_count += 1

        day = _usage_window(session, principal_id, "day", now)
        if (
            day.request_count + day.reserved_requests
            >= self.settings.principal_daily_request_limit
        ):
            raise UsageGateError("daily_quota_exceeded", 403)

        month = _usage_window(session, principal_id, "month", now)
        if (
            month.request_count + month.reserved_requests
            >= self.settings.principal_monthly_request_limit
        ):
            raise UsageGateError("monthly_quota_exceeded", 403)

        global_start = _window_start(now, "month")
        budget = session.get(
            GlobalBudgetWindow, global_start, with_for_update=True
        )
        if budget is None:
            budget = GlobalBudgetWindow(window_start=global_start)
            session.add(budget)
            session.flush()
        if (
            budget.settled_cost_cny
            + budget.reserved_cost_cny
            + self.reservation
            > Decimal(str(self.settings.global_monthly_budget_cny))
        ):
            raise UsageGateError("global_budget_exhausted", 503)

        day.reserved_requests += 1
        month.reserved_requests += 1
        budget.reserved_cost_cny += self.reservation

    def settle(
        self, session: Session, principal_id: str, usage: TokenUsage
    ) -> None:
        now = datetime.now(timezone.utc)
        session.get(Principal, principal_id, with_for_update=True)
        cost = Decimal(str(usage.estimated_cost_cny))
        for kind in ("day", "month"):
            window = _usage_window(session, principal_id, kind, now)
            window.reserved_requests = max(window.reserved_requests - 1, 0)
            window.request_count += 1
            window.input_tokens += usage.input_tokens
            window.output_tokens += usage.output_tokens
            window.cache_tokens += usage.cache_hit_tokens
            window.estimated_cost_cny += cost
        budget = session.get(
            GlobalBudgetWindow, _window_start(now, "month"), with_for_update=True
        )
        if budget is None:
            raise RuntimeError("missing global budget reservation")
        budget.reserved_cost_cny = max(
            budget.reserved_cost_cny - self.reservation, Decimal("0")
        )
        budget.settled_cost_cny += cost

    def release(self, session: Session, principal_id: str) -> None:
        now = datetime.now(timezone.utc)
        session.get(Principal, principal_id, with_for_update=True)
        for kind in ("day", "month"):
            window = _usage_window(session, principal_id, kind, now)
            window.reserved_requests = max(window.reserved_requests - 1, 0)
        budget = session.get(
            GlobalBudgetWindow, _window_start(now, "month"), with_for_update=True
        )
        if budget is not None:
            budget.reserved_cost_cny = max(
                budget.reserved_cost_cny - self.reservation, Decimal("0")
            )

    def snapshot(self, session: Session, principal_id: str) -> UsageSnapshot:
        now = datetime.now(timezone.utc)
        day = _usage_window(session, principal_id, "day", now)
        month = _usage_window(session, principal_id, "month", now)
        return UsageSnapshot(
            daily_used=day.request_count,
            monthly_used=month.request_count,
        )


def with_estimated_cost(usage: TokenUsage, *, deep_mode: bool) -> TokenUsage:
    uncached = max(usage.input_tokens - usage.cache_hit_tokens, 0)
    if deep_mode:
        input_rate, cache_rate, output_rate = (
            PRO_INPUT_CNY_PER_MILLION,
            PRO_CACHE_CNY_PER_MILLION,
            PRO_OUTPUT_CNY_PER_MILLION,
        )
    else:
        input_rate, cache_rate, output_rate = (
            FLASH_INPUT_CNY_PER_MILLION,
            FLASH_CACHE_CNY_PER_MILLION,
            FLASH_OUTPUT_CNY_PER_MILLION,
        )
    cost = (
        uncached * input_rate
        + usage.cache_hit_tokens * cache_rate
        + usage.output_tokens * output_rate
    ) / 1_000_000
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_hit_tokens=usage.cache_hit_tokens,
        estimated_cost_cny=round(cost, 8),
    )
