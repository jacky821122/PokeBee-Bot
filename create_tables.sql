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

CREATE TABLE IF NOT EXISTS modifier_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- date range this record covers
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,

    -- modifier info
    name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    total_price_change REAL NOT NULL DEFAULT 0.0,

    -- metadata
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

