import sqlite3

import metrics_common


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


def _seed_rows(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.executescript(CREATE_MODIFIER_TABLE)
    conn.executemany(
        """
        INSERT INTO modifier_summary
            (start_date, end_date, name, count, total_price_change, source_file, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-02-22", "2026-02-28", "加購一份雞胸肉 80g", 2, 100.0, "m.csv", "2026-03-01T00:00:00"),
            ("2026-02-22", "2026-02-28", "七味粉", 3, 45.0, "m.csv", "2026-03-01T00:00:00"),
            ("2026-02-22", "2026-02-28", "加購一份生鮪魚 45g", 1, 70.0, "m.csv", "2026-03-01T00:00:00"),
        ],
    )
    conn.commit()
    conn.close()


def test_load_modifier_defaults_to_protein_only(tmp_path, monkeypatch):
    db_path = tmp_path / "modifier.db"
    _seed_rows(db_path)
    monkeypatch.setattr(metrics_common, "DB_PATH", str(db_path))

    df = metrics_common.load_modifier("2026-02-22", "2026-02-28")

    assert set(df["name"].tolist()) == {"加購一份雞胸肉 80g", "加購一份生鮪魚 45g"}


def test_load_modifier_can_return_all_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "modifier.db"
    _seed_rows(db_path)
    monkeypatch.setattr(metrics_common, "DB_PATH", str(db_path))

    df = metrics_common.load_modifier("2026-02-22", "2026-02-28", protein_only=False)

    assert set(df["name"].tolist()) == {"加購一份雞胸肉 80g", "七味粉", "加購一份生鮪魚 45g"}
