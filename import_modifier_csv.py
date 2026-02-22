import argparse
import re
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime
from metrics_common import DB_PATH, PROTEIN_RULES, PROTEIN_KEYWORDS

def import_modifier_csv(csv_path: str):
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    match = re.search(r"(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})", csv_path.name)
    if not match:
        raise ValueError("Filename does not contain valid date range")

    start_date, end_date = match.groups()

    df = pd.read_csv(csv_path)

    # 僅保留蛋白質加購
    df = df[df["name"].str.contains("|".join(PROTEIN_KEYWORDS), na=False)]

    # 清理數值欄位
    df["count"] = pd.to_numeric(df["Count"], errors="coerce").fillna(0).astype(int)
    df["total_price_change"] = pd.to_numeric(df["Total price change"], errors="coerce").fillna(0.0)

    df["start_date"] = start_date
    df["end_date"] = end_date
    df["source_file"] = csv_path.name
    df["imported_at"] = datetime.now().isoformat(timespec="seconds")

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    cur = conn.cursor()

    inserted = 0

    try:
        cur.execute("BEGIN")

        # 刪除重疊區間
        cur.execute("""
            DELETE FROM modifier_summary
            WHERE NOT (end_date < ? OR start_date > ?)
        """, (start_date, end_date))

        for _, row in df.iterrows():
            cur.execute("""
                INSERT INTO modifier_summary (
                    start_date,
                    end_date,
                    name,
                    count,
                    total_price_change,
                    source_file,
                    imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row["start_date"],
                row["end_date"],
                row["name"],
                row["count"],
                row["total_price_change"],
                row["source_file"],
                row["imported_at"],
            ))
            inserted += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"Modifier import finished: rows={inserted}")
    return f"Modifier import finished: rows={inserted}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to iCHEF Modifier CSV file")
    args = parser.parse_args()

    import_modifier_csv(args.file)

