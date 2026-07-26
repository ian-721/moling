"""M0-B persistent identity, profile, usage, and idempotency tables."""

from alembic import op
import sqlalchemy as sa

revision = "20260726_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "principals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("principal_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "registration_windows",
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "global_budget_windows",
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column(
            "settled_cost_cny",
            sa.Numeric(14, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reserved_cost_cny",
            sa.Numeric(14, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assistant_profiles",
        sa.Column(
            "principal_id",
            sa.String(36),
            sa.ForeignKey("principals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("assistant_name", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "device_installations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(36),
            sa.ForeignKey("principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("installation_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_device_installations_principal_id",
        "device_installations",
        ["principal_id"],
    )
    op.create_table(
        "access_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(36),
            sa.ForeignKey("principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_access_tokens_principal_id", "access_tokens", ["principal_id"])
    op.create_table(
        "usage_windows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(36),
            sa.ForeignKey("principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("window_kind", sa.String(16), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("reserved_requests", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "estimated_cost_cny",
            sa.Numeric(14, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "principal_id",
            "window_kind",
            "window_start",
            name="uq_usage_principal_window",
        ),
    )
    op.create_index("ix_usage_windows_principal_id", "usage_windows", ["principal_id"])
    op.create_table(
        "reply_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(36),
            sa.ForeignKey("principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("provider", sa.String(32)),
        sa.Column("model", sa.String(64)),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "estimated_cost_cny",
            sa.Numeric(14, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column("response_snapshot", sa.Text()),
        sa.Column("error_category", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "principal_id",
            "request_id",
            name="uq_reply_principal_request",
        ),
    )
    op.create_index("ix_reply_requests_principal_id", "reply_requests", ["principal_id"])
    op.create_index(
        "ix_reply_lease",
        "reply_requests",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_table("reply_requests")
    op.drop_table("usage_windows")
    op.drop_table("access_tokens")
    op.drop_table("device_installations")
    op.drop_table("assistant_profiles")
    op.drop_table("global_budget_windows")
    op.drop_table("registration_windows")
    op.drop_table("principals")
