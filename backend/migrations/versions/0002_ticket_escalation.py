"""Add technician ticket escalation state."""

import sqlalchemy as sa
from alembic import op

revision = "0002_ticket_escalation"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tickets",
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("tickets", "escalated")
