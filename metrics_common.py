import sqlite3
from pathlib import Path
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

# 基準價格表（原價，未折扣）
BOWL_BASE_PRICES = {
    "雞胸肉自選碗": 160,
    "鮮蝦自選碗": 170,
    "嚴選生鮭魚自選碗": 190,
    "生鮪魚自選碗": 180,
    "豆腐自選碗": 125,
    "均衡經典碗": 170,
    "高蛋白健身碗": 220,
    "清爽佛陀碗": 130,
    "海味雙魚碗": 260,
}

# 試營運折扣係數
DISCOUNT_FACTOR = 0.9

# 常見加購價格（可依營運實際價格調整）
KNOWN_ADDON_PRICES = [15, 30, 50, 60, 70, 80, 90]
MAX_ADDON_PER_BOWL = 220
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

SET_MEAL_RULES = {
    "均衡經典碗": {"chicken": 1},
    "高蛋白健身碗": {"chicken": 2},
    "清爽佛陀碗": {"tofu": 1},
    "海味雙魚碗": {"salmon": 1, "tuna": 1},
}

_PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = str(_PROJECT_ROOT / "data" / "db" / "ichef.db")

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
    if not isinstance(items_text, str):
        return []
    return [item.strip() for item in items_text.split(",") if item.strip()]

def _is_valid_bowl_item(item: str) -> bool:
    return (
        any(keyword in item for keyword in BOWLS_KEYWORDS)
        and not any(excluded in item for excluded in EXCLUDE_ITEMS)
    )

def count_bowls(items_text: str) -> int:
    """基礎碗數計算（每個項目算 1 碗，不考慮數量）"""
    items = _split_items(items_text)
    return sum(1 for item in items if _is_valid_bowl_item(item))

def infer_quantity_from_price(item_name: str, price: float) -> int:
    """
    從價格推斷數量（處理同一品項點多份的情況）

    如果價格是基準價格的整數倍（允許 ±5 元誤差），返回數量；否則返回 1。
    這樣可以正確處理「客人點了 3 碗一樣的雞胸肉」的情況。
    """
    # 找到對應的基準價格
    base_price = None
    for bowl_name, bp in BOWL_BASE_PRICES.items():
        if bowl_name in item_name:
            base_price = bp
            break

    if base_price is None:
        return 1  # 未知品項，預設 1

    # 計算理論上的原價
    original_price = price / DISCOUNT_FACTOR
    tolerance = 5

    # 嘗試由高到低推 quantity，盡量捕捉「同款多碗 + 每碗相同加購」的情境
    max_candidate = max(1, int(round(original_price / base_price)) + 1)
    for quantity in range(max_candidate, 0, -1):
        per_bowl_original = original_price / quantity
        addon_per_bowl = per_bowl_original - base_price

        if addon_per_bowl < -tolerance:
            continue

        if abs(addon_per_bowl) <= tolerance:
            return quantity

        if addon_per_bowl > MAX_ADDON_PER_BOWL:
            continue

        if _is_plausible_addon_amount(addon_per_bowl, tolerance=2):
            return quantity

    return 1  # fallback：保守視為 1 碗


def _is_plausible_addon_amount(amount: float, *, tolerance: int = 5) -> bool:
    """判斷加購金額是否可能由常見加購單價組合而成。"""
    if amount < 0:
        return False

    target = int(round(amount))
    # 無界背包：檢查是否可由常見加購價格湊出 target（允許 ±tolerance）
    reachable = [False] * (target + tolerance + 1)
    reachable[0] = True

    for subtotal in range(len(reachable)):
        if not reachable[subtotal]:
            continue
        for addon_price in KNOWN_ADDON_PRICES:
            next_total = subtotal + addon_price
            if next_total < len(reachable):
                reachable[next_total] = True

    low = max(0, target - tolerance)
    high = min(len(reachable) - 1, target + tolerance)
    return any(reachable[value] for value in range(low, high + 1))

def count_bowls_smart(items_text: str) -> int:
    """
    智能碗數計算（考慮數量推斷）

    從價格推斷是否為多份同一品項，能正確處理：
    - 雞胸肉自選碗 $432 → 3 碗（160 × 3 × 0.9）
    - 雞胸肉自選碗 $216 → 1 碗（有加購，不是整數倍）
    """
    items = _split_items(items_text)
    total_bowls = 0

    for item in items:
        if not _is_valid_bowl_item(item):
            continue

        # 解析價格
        if "$" in item:
            try:
                name, price_str = item.rsplit("$", 1)
                price = float(price_str)
                quantity = infer_quantity_from_price(name.strip(), price)
                total_bowls += quantity
            except ValueError:
                total_bowls += 1  # 解析失敗，算 1 碗
        else:
            total_bowls += 1  # 沒有價格資訊，算 1 碗

    return total_bowls

def filter_protein_bowls(items_text: str) -> list[str]:
    items = _split_items(items_text)
    return [item for item in items if _is_valid_bowl_item(item) and any(keyword in item for keyword in PROTEIN_KEYWORDS)]

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

def filter_protein_non_bowls(items_text: str) -> list[str]:
    items = _split_items(items_text)
    return [
        item
        for item in items
        if not _is_valid_bowl_item(item)
        and any(keyword in item for keyword in PROTEIN_KEYWORDS)
    ]

def count_protein_non_bowls(items_text: str, protein_key: str) -> int:
    required_keywords = PROTEIN_RULES[protein_key]
    items = _split_items(items_text)
    return sum(
        1
        for item in items
        if not _is_valid_bowl_item(item)
        and all(keyword in item for keyword in required_keywords)
    )

def count_set_meal_proteins(items_text: str) -> dict[str, int]:
    items = _split_items(items_text)
    protein_counts = {protein: 0 for protein in PROTEIN_RULES}  # 初始化

    for item in items:
        for meal_name, protein_map in SET_MEAL_RULES.items():
            if meal_name in item:
                for protein, qty in protein_map.items():
                    protein_counts[protein] += qty
    return protein_counts

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
        SELECT name, SUM(count) AS count
        FROM modifier_summary
        WHERE NOT (end_date < ? OR start_date > ?)
        GROUP BY name;
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        if df.empty:
            return pd.DataFrame(columns=["name", "count"])
        return df
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

def validate_bowl_counts(total_bowls: int, protein_bowls: dict, protein_set_meals: dict) -> None:
    """
    驗證碗數統計的一致性

    檢查總碗數是否與各分類碗數總和接近，防止配置錯誤（如套餐名稱錯誤）。
    允許小誤差（因為可能有部分碗沒有蛋白質標記）。
    """
    protein_bowl_sum = sum(protein_bowls.values())
    set_meal_sum = sum(protein_set_meals.values())
    calculated_total = protein_bowl_sum + set_meal_sum

    # 允許 5 碗的誤差（例如豆腐自選碗可能沒有被正確分類）
    diff = abs(total_bowls - calculated_total)
    if diff > 5:
        print(f"⚠️  碗數統計異常：總碗數 {total_bowls} vs 分類總和 {calculated_total} (差異: {diff})")
        print(f"   蛋白質碗: {protein_bowl_sum}, 套餐: {set_meal_sum}")
        print(f"   請檢查 SET_MEAL_RULES 和 PROTEIN_RULES 配置是否正確")
