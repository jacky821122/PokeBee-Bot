CREATE TABLE IF NOT EXISTS raw_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- metadata
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL,

    -- order identifiers
    invoice_number TEXT,
    order_id TEXT,

    -- time
    checkout_time TEXT,

    -- order info
    order_source TEXT,
    order_type TEXT,

    -- money
    discount_amount REAL,
    invoice_amount REAL,

    -- payment
    payment_method TEXT,

    -- status
    order_status TEXT,

    -- raw items text (DO NOT PARSE NOW)
    items_text TEXT,

    -- dedup key
    UNIQUE(invoice_number, checkout_time)
);

