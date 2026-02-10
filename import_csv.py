import argparse
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = "data/db/ichef.db"

COLUMN_MAP = {
    "Receipt number": "invoice_number",
    "Running Receipt Number": "order_id",
    "payment time": "checkout_time",
    "Order source": "order_source",
    "Order Type": "order_type",
    "Discount amount": "discount_amount",
    "Invoice Amount": "invoice_amount",
    "Payment Module": "payment_method",
    "Current Status": "order_status",
    "items": "items_text"
}


def import_csv(csv_path: str):
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    df = pd.read_csv(csv_path)

    # only keep columns we care about
    df = df[list(COLUMN_MAP.keys())].rename(columns=COLUMN_MAP)

    # normalize time
    df["checkout_time"] = pd.to_datetime(df["checkout_time"]).astype(str)

    # add metadata
    df["source_file"] = csv_path.name
    df["imported_at"] = datetime.now().isoformat(timespec="seconds")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO raw_orders (
                    source_file,
                    imported_at,
                    invoice_number,
                    order_id,
                    checkout_time,
                    order_source,
                    order_type,
                    discount_amount,
                    invoice_amount,
                    payment_method,
                    order_status,
                    items_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(row[col] for col in [
                    "source_file",
                    "imported_at",
                    "invoice_number",
                    "order_id",
                    "checkout_time",
                    "order_source",
                    "order_type",
                    "discount_amount",
                    "invoice_amount",
                    "payment_method",
                    "order_status",
                    "items_text"
                ])
            )
            if cur.rowcount == 0:
                skipped += 1
            else:
                inserted += 1
        except Exception as e:
            print(f"Error inserting row: {e}")

    conn.commit()
    conn.close()

    print(f"Import finished: inserted={inserted}, skipped={skipped}")
    return f"Import finished: inserted={inserted}, skipped={skipped}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to iCHEF CSV file")
    args = parser.parse_args()

    import_csv(args.file)

