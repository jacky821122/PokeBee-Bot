import sqlite3
from typing import Iterable, Optional
import pandas as pd

# --- 設定區：未來更動這裡即可 ---
BUSINESS_HOURS = {
    "lunch": {"start": "11:00", "end": "14:30"},
    "dinner": {"start": "16:30", "end": "20:00"},
}

# 定義碗關鍵字與排除清單
BOWLS_KEYWORDS = ["碗"]
EXCLUDE_ITEMS = ["提袋", "加購"]
# ----------------------------

# 蛋白質辨識規則
PROTEIN_RULES = {
    "chicken": ["雞胸肉"],
    "tofu": ["豆腐"],
    "shrimp": ["鮮蝦"],
    "salmon": ["鮭魚"],
    "tuna": ["鮪魚"],
}
PROTEIN_KEYWORDS = [keyword for sublist in PROTEIN_RULES.values() for keyword in sublist]
# ----------------------------

DB_PATH = "data/db/ichef.db"

def is_in_period(dt, period_name: str) -> bool:
    """判斷時間是否在設定的營業時間內"""
    start = pd.to_datetime(BUSINESS_HOURS[period_name]["start"]).time()
    end = pd.to_datetime(BUSINESS_HOURS[period_name]["end"]).time()
    return start <= dt.time() <= end

def normalize_payment(payment_method: Optional[str]) -> str:
    if not payment_method:
        return "Other"
    if "現金" in payment_method or "Cash" in payment_method:
        return "Cash"
    if "Line" in payment_method:
        return "LinePay"
    return "Other"

def _split_items(items_text: str):
    if not items_text:
        return []
    return [item.strip() for item in items_text.split(",") if item.strip()]

def _is_valid_bowl_item(item: str) -> bool:
    return (
        any(keyword in item for keyword in BOWLS_KEYWORDS)
        and not any(excluded in item for excluded in EXCLUDE_ITEMS)
    )

def count_bowls(items_text: str) -> int:
    items = _split_items(items_text)
    return sum(1 for item in items if _is_valid_bowl_item(item))

def count_protein_bowls(items_text: str, protein_key: str) -> int:
    """計算指定蛋白質的碗數（需符合蛋白質關鍵字 + 碗，且排除非主餐項目）"""
    required_keywords = PROTEIN_RULES[protein_key]
    items = _split_items(items_text)
    return sum(
        1
        for item in items
        if _is_valid_bowl_item(item)
        and all(keyword in item for keyword in required_keywords)
    )

def count_protein_from_modifiers(name: str, protein_key: str) -> int:
    required_keywords = PROTEIN_RULES[protein_key]
    return 1 if all(keyword in name for keyword in required_keywords) else 0

def load_orders(start_date: str, end_date: str, *, columns: list[str]) -> pd.DataFrame:
    """
    載入日期區間內訂單，並先行過濾作廢單。

    start_date, end_date: YYYY-MM-DD
    區間為 [start_date, end_date + 1 day)
    """
    select_columns = ",\n            ".join(columns)
    query = f"""
        SELECT
            {select_columns}
        FROM raw_orders
        WHERE checkout_time >= ?
          AND checkout_time < date(?, '+1 day')
          AND order_status NOT LIKE '%Voided%'
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, conn, params=(start_date, end_date))
    finally:
        conn.close()

def load_modifier(start_date: str, end_date: str) -> pd.DataFrame:
    query = f"""
        SELECT name, count
        FROM modifier_summary
        WHERE NOT (end_date < ? OR start_date > ?)
        GROUP BY name;
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, conn, params=(start_date, end_date))
    finally:
        conn.close()

def preprocess_orders(df: pd.DataFrame) -> pd.DataFrame:
    """套用共用前處理：去除 invoice_amount <= 0、轉 datetime。"""
    if df.empty:
        return df.copy()

    prepared = df[df["invoice_amount"] > 0].copy()
    if prepared.empty:
        return prepared

    prepared["checkout_time"] = pd.to_datetime(prepared["checkout_time"])
    return prepared