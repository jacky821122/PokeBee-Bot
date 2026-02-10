import pandas as pd

# --- 設定區：未來更動這裡即可 ---
BUSINESS_HOURS = {
    "lunch": {"start": "11:00", "end": "14:30"},
    "dinner": {"start": "16:30", "end": "20:00"},
}

# 定義主餐關鍵字與排除清單
MAIN_DISH_KEYWORDS = ["碗"]
EXCLUDE_ITEMS = ["提袋", "加購"]
# ----------------------------

DB_PATH = "data/db/ichef.db"


def is_in_period(dt, period_name):
    """判斷時間是否在設定的營業時間內"""
    start = pd.to_datetime(BUSINESS_HOURS[period_name]["start"]).time()
    end = pd.to_datetime(BUSINESS_HOURS[period_name]["end"]).time()
    return start <= dt.time() <= end


def normalize_payment(p):
    if not p:
        return "Other"
    if "現金" in p or "Cash" in p:
        return "Cash"
    if "Line" in p:
        return "LinePay"
    return "Other"


def count_main_dishes(items_text: str) -> int:
    if not items_text:
        return 0
    items = items_text.split(",")
    return sum(
        1
        for item in items
        if any(keyword in item for keyword in MAIN_DISH_KEYWORDS)
        and not any(excluded in item for excluded in EXCLUDE_ITEMS)
    )
