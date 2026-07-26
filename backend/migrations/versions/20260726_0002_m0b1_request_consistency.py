"""Persist provider boundary and original quota reservation windows."""

from alembic import op
import sqlalchemy as sa

revision = "20260726_0002"
down_revision = "20260726_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reply_requests") as batch:
        batch.add_column(sa.Column("provider_started_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column("reservation_day_start", sa.DateTime(timezone=True))
        )
        batch.add_column(
            sa.Column("reservation_month_start", sa.DateTime(timezone=True))
        )
        batch.add_column(sa.Column("budget_month_start", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("reserved_cost_cny", sa.Numeric(14, 8)))
        batch.add_column(sa.Column("reservation_state", sa.String(24)))

    # A pre-M0-B.1 processing row cannot prove whether its provider call began
    # and has no persisted reservation keys. Freeze it directly as unknown;
    # keeping its old reservation is conservative and avoids corrupting a new
    # quota window during upgrade.
    op.execute(
        "UPDATE reply_requests "
        "SET status = 'outcome_unknown', "
        "provider_started_at = updated_at, "
        "error_category = 'request_outcome_unknown', "
        "lease_expires_at = NULL "
        "WHERE status = 'processing'"
    )


def downgrade() -> None:
    with op.batch_alter_table("reply_requests") as batch:
        batch.drop_column("reservation_state")
        batch.drop_column("reserved_cost_cny")
        batch.drop_column("budget_month_start")
        batch.drop_column("reservation_month_start")
        batch.drop_column("reservation_day_start")
        batch.drop_column("provider_started_at")
