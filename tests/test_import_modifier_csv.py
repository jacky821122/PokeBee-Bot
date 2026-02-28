import sqlite3

import pandas as pd

import import_modifier_csv


CREATE_MODIFIER_TABLE = """
CREATE TABLE modifier_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    total_price_change REAL NOT NULL DEFAULT 0.0,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
"""


def test_import_modifier_keeps_sukiyaki_pork_row(tmp_path, monkeypatch):
    db_path = tmp_path / "modifier.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_MODIFIER_TABLE)
    conn.close()

    monkeypatch.setattr(import_modifier_csv, "DB_PATH", str(db_path))

    csv_path = tmp_path / "modifier-2026-02-22~2026-02-28.csv"
    pd.DataFrame(
        [
            {"name": "加購一份壽喜燒豬", "Count": 3, "Total price change": 150},
            {"name": "  ", "Count": 99, "Total price change": 0},
        ]
    ).to_csv(csv_path, index=False)

    import_modifier_csv.import_modifier_csv(str(csv_path))

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name, count FROM modifier_summary ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("加購一份壽喜燒豬", 3)]
