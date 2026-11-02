"""Create inventory tables and append-only ledger protections."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("unit_price_minor", sa.Integer(), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("sku"),
        sa.CheckConstraint("unit_price_minor BETWEEN 0 AND 2147483647", name="ck_product_price"),
        sa.CheckConstraint("low_stock_threshold BETWEEN 0 AND 2147483647", name="ck_product_threshold"),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 160", name="ck_product_name"),
        sa.CheckConstraint("length(trim(category)) BETWEEN 1 AND 80", name="ck_product_category"),
        sa.CheckConstraint("length(sku) BETWEEN 1 AND 64 AND sku = upper(sku)", name="ck_product_sku"),
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("movement_type", sa.String(16), nullable=False),
        sa.Column("quantity_change", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(movement_type = 'OPENING' AND quantity_change >= 0) OR "
            "(movement_type = 'RECEIVED' AND quantity_change > 0) OR "
            "(movement_type = 'ISSUED' AND quantity_change < 0) OR "
            "(movement_type = 'ADJUSTMENT' AND quantity_change != 0)", name="ck_movement_sign",
        ),
        sa.CheckConstraint("quantity_change BETWEEN -2147483647 AND 2147483647", name="ck_movement_quantity"),
        sa.CheckConstraint("length(trim(reason)) BETWEEN 1 AND 500", name="ck_movement_reason"),
    )
    op.create_index("ix_movements_product_created", "stock_movements", ["product_id", "created_at", "id"])
    op.create_index("ix_movements_created", "stock_movements", ["created_at", "id"])
    op.create_index("uq_movement_opening", "stock_movements", ["product_id"], unique=True, sqlite_where=sa.text("movement_type = 'OPENING'"))
    # Defense in depth: movements can only be corrected by appending another one.
    op.execute("CREATE TRIGGER movements_no_update BEFORE UPDATE ON stock_movements BEGIN SELECT RAISE(ABORT, 'Movements are immutable'); END")
    op.execute("CREATE TRIGGER movements_no_delete BEFORE DELETE ON stock_movements BEGIN SELECT RAISE(ABORT, 'Movements are immutable'); END")


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS movements_no_update")
    op.execute("DROP TRIGGER IF EXISTS movements_no_delete")
    op.drop_table("stock_movements")
    op.drop_table("products")
