from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_database_url


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def migrate_schema() -> None:
    """SQLite: add address_* columns when upgrading from older schema with address_line."""
    insp = inspect(engine)
    if "orders" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("orders")}
    with engine.begin() as conn:
        if "address_street" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN address_street TEXT"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN address_city TEXT"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN address_zip TEXT"))
        if "address_line" in cols:
            conn.execute(
                text(
                    "UPDATE orders SET address_street = address_line "
                    "WHERE (address_street IS NULL OR TRIM(address_street) = '') "
                    "AND address_line IS NOT NULL AND TRIM(address_line) != ''"
                )
            )
        if "ticket_unit_price_czk" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN ticket_unit_price_czk REAL"))
        tito_cols = {
            "tito_invoice_release_id": "INTEGER",
            "tito_invoice_release_slug": "VARCHAR(255)",
            "tito_public_quantity_before": "INTEGER",
            "tito_public_quantity_after": "INTEGER",
            "tito_quantity_held_at": "DATETIME",
            "tito_quantity_released_at": "DATETIME",
            "tito_invoice_quantity_before": "INTEGER",
            "tito_invoice_quantity_after": "INTEGER",
            "tito_invoice_quantity_patched_at": "DATETIME",
        }
        for name, sql_type in tito_cols.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {sql_type}"))
        admin_cols = {
            "error_code": "VARCHAR(64)",
            "error_step": "VARCHAR(128)",
            "paid_customer_email_sent_at": "DATETIME",
            "manual_final_invoice_request_sent_at": "DATETIME",
        }
        for name, sql_type in admin_cols.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {sql_type}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
