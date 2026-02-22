import sqlite3, pytest
import metrics_common

CREATE_TABLES = """
CREATE TABLE raw_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    invoice_number TEXT,
    order_id TEXT,
    checkout_time TEXT,
    order_source TEXT,
    order_type TEXT,
    discount_amount REAL,
    invoice_amount REAL,
    payment_method TEXT,
    order_status TEXT,
    items_text TEXT,
    UNIQUE(invoice_number, checkout_time)
);
"""

@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(CREATE_TABLES)
    conn.close()
    monkeypatch.setattr(metrics_common, "DB_PATH", str(db_path))
    return db_path

_order_counter = 0

def insert_order(db_path, *, checkout_time, items_text, invoice_amount,
                 order_type="Dine In", order_source="On site",
                 payment_method="現金(Cash payment module)",
                 order_status="Issued", discount_amount=0):
    global _order_counter
    _order_counter += 1
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        INSERT INTO raw_orders
          (source_file, imported_at, invoice_number, checkout_time,
           order_source, order_type, discount_amount, invoice_amount,
           payment_method, order_status, items_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("test.csv", "2026-01-01T00:00:00", f"INV-{_order_counter:05d}",
          checkout_time, order_source, order_type, discount_amount,
          invoice_amount, payment_method, order_status, items_text))
    conn.commit()
    conn.close()
