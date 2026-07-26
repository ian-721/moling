from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.db_models import GlobalBudgetWindow, Principal, ReplyRequest, UsageWindow
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
    session: Session, principal_id: str, kind: str, window_start: datetime
) -> UsageWindow:
    window = (
        session.query(UsageWindow)
        .filter_by(
            principal_id=principal_id,
            window_kind=kind,
            window_start=window_start,
        )
        .with_for_update()
        .one_or_none()
    )
    if window is None:
        window = UsageWindow(
            principal_id=principal_id,
            window_kind=kind,
            window_start=window_start,
        )
        session.add(window)
        session.flush()
    return window


def _existing_usage_window(
    session: Session, principal_id: str, kind: str, window_start: datetime
) -> UsageWindow:
    window = (
        session.query(UsageWindow)
        .filter_by(
            principal_id=principal_id,
            window_kind=kind,
            window_start=window_start,
        )
        .with_for_update()
        .one_or_none()
    )
    if window is None:
        raise RuntimeError(f"missing {kind} quota reservation window")
    return window


def _global_budget_window(
    session: Session, window_start: datetime
) -> GlobalBudgetWindow:
    dialect = session.get_bind().dialect.name
    values = {
        "window_start": window_start,
        "settled_cost_cny": Decimal("0"),
        "reserved_cost_cny": Decimal("0"),
    }
    if dialect == "postgresql":
        session.execute(
            postgresql_insert(GlobalBudgetWindow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["window_start"])
        )
    elif dialect == "sqlite":
        session.execute(
            sqlite_insert(GlobalBudgetWindow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["window_start"])
        )
    else:
        existing = session.get(GlobalBudgetWindow, window_start)
        if existing is None:
            session.add(GlobalBudgetWindow(**values))
            session.flush()
    budget = session.get(GlobalBudgetWindow, window_start, with_for_update=True)
    if budget is None:
        raise RuntimeError("failed to create global budget window")
    return budget


class UsageService:
    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.reservation = Decimal(str(settings.request_cost_reservation_cny))
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def reserve(self, session: Session, request: ReplyRequest) -> None:
        if request.reservation_state == "reserved":
            raise RuntimeError("request already has an active reservation")
        now = self.clock()
        principal_id = request.principal_id
        # Locking the principal serializes all quota reservations for this
        # identity across workers and application instances.
        principal = session.get(Principal, principal_id, with_for_update=True)
        if principal is None or principal.status != "active":
            raise UsageGateError("invalid_principal", 401)

        minute_start = _window_start(now, "minute")
        day_start = _window_start(now, "day")
        month_start = _window_start(now, "month")
        minute = _usage_window(session, principal_id, "minute", minute_start)
        if minute.request_count >= self.settings.principal_requests_per_minute:
            raise UsageGateError("rate_limit_exceeded", 429)
        minute.request_count += 1

        day = _usage_window(session, principal_id, "day", day_start)
        if (
            day.request_count + day.reserved_requests
            >= self.settings.principal_daily_request_limit
        ):
            raise UsageGateError("daily_quota_exceeded", 403)

        month = _usage_window(session, principal_id, "month", month_start)
        if (
            month.request_count + month.reserved_requests
            >= self.settings.principal_monthly_request_limit
        ):
            raise UsageGateError("monthly_quota_exceeded", 403)

        budget = _global_budget_window(session, month_start)
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
        request.reservation_day_start = day_start
        request.reservation_month_start = month_start
        request.budget_month_start = month_start
        request.reserved_cost_cny = self.reservation
        request.reservation_state = "reserved"

    def settle(
        self, session: Session, request: ReplyRequest, usage: TokenUsage
    ) -> None:
        if request.reservation_state == "settled":
            return
        if request.reservation_state != "reserved":
            raise RuntimeError("request has no active reservation to settle")
        principal_id = request.principal_id
        session.get(Principal, principal_id, with_for_update=True)
        cost = Decimal(str(usage.estimated_cost_cny))
        starts = {
            "day": request.reservation_day_start,
            "month": request.reservation_month_start,
        }
        for kind, start in starts.items():
            if start is None:
                raise RuntimeError(f"missing persisted {kind} reservation key")
            window = _existing_usage_window(session, principal_id, kind, start)
            if window.reserved_requests <= 0:
                raise RuntimeError(f"{kind} reservation underflow")
            window.reserved_requests -= 1
            window.request_count += 1
            window.input_tokens += usage.input_tokens
            window.output_tokens += usage.output_tokens
            window.cache_tokens += usage.cache_hit_tokens
            window.estimated_cost_cny += cost
        if request.budget_month_start is None or request.reserved_cost_cny is None:
            raise RuntimeError("missing persisted budget reservation key")
        budget = session.get(
            GlobalBudgetWindow,
            request.budget_month_start,
            with_for_update=True,
        )
        if budget is None:
            raise RuntimeError("missing global budget reservation")
        if budget.reserved_cost_cny < request.reserved_cost_cny:
            raise RuntimeError("global budget reservation underflow")
        budget.reserved_cost_cny -= request.reserved_cost_cny
        budget.settled_cost_cny += cost
        request.reservation_state = "settled"

    def conservative_settle(self, session: Session, request: ReplyRequest) -> None:
        if request.reservation_state == "settled":
            return
        if request.reserved_cost_cny is None:
            raise RuntimeError("missing conservative reservation cost")
        self.settle(
            session,
            request,
            TokenUsage(estimated_cost_cny=float(request.reserved_cost_cny)),
        )

    def release(self, session: Session, request: ReplyRequest) -> None:
        if request.reservation_state == "released":
            return
        if request.reservation_state != "reserved":
            raise RuntimeError("request has no active reservation to release")
        principal_id = request.principal_id
        session.get(Principal, principal_id, with_for_update=True)
        starts = {
            "day": request.reservation_day_start,
            "month": request.reservation_month_start,
        }
        for kind, start in starts.items():
            if start is None:
                raise RuntimeError(f"missing persisted {kind} reservation key")
            window = _existing_usage_window(session, principal_id, kind, start)
            if window.reserved_requests <= 0:
                raise RuntimeError(f"{kind} reservation underflow")
            window.reserved_requests -= 1
        if request.budget_month_start is None or request.reserved_cost_cny is None:
            raise RuntimeError("missing persisted budget reservation key")
        budget = session.get(
            GlobalBudgetWindow,
            request.budget_month_start,
            with_for_update=True,
        )
        if budget is None:
            raise RuntimeError("missing global budget reservation")
        if budget.reserved_cost_cny < request.reserved_cost_cny:
            raise RuntimeError("global budget reservation underflow")
        budget.reserved_cost_cny -= request.reserved_cost_cny
        request.reservation_state = "released"

    def snapshot(self, session: Session, principal_id: str) -> UsageSnapshot:
        now = self.clock()
        day = _usage_window(
            session, principal_id, "day", _window_start(now, "day")
        )
        month = _usage_window(
            session, principal_id, "month", _window_start(now, "month")
        )
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
