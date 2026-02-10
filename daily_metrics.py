import argparse
import sqlite3
import pandas as pd
from metrics_common import (
    BUSINESS_HOURS,
    DB_PATH,
    PROTEIN_RULES,
    count_main_dishes,
    count_protein_bowls,
    is_in_period,
    normalize_payment,
)


def calculate_daily_metrics(target_date: str):
    conn = sqlite3.connect(DB_PATH)

    # 優化 1: 增加 Current Status 過濾，避免計入作廢訂單
    # 優化 2: 預先過濾欄位，減少記憶體佔用
    query = """
        SELECT
            checkout_time,
            order_source,
            order_type,
            discount_amount,
            invoice_amount,
            payment_method,
            order_status,
            items_text
        FROM raw_orders
        WHERE checkout_time >= ? AND checkout_time < date(?, '+1 day')
        AND order_status NOT LIKE '%Voided%'
    """

    df = pd.read_sql_query(query, conn, params=(target_date, target_date))
    conn.close()

    if df.empty:
        return None

    # 1. 過濾員工餐與無效訂單
    # 邏輯：排除金額為 0 的訂單（視為員工餐或公關單）
    df = df[df["invoice_amount"] > 0].copy()

    # 2. 時間處理
    df["checkout_time"] = pd.to_datetime(df["checkout_time"])
    df["hour"] = df["checkout_time"].dt.hour

    # 3. 計算碗數 (主餐數)
    df["dish_qty"] = df["items_text"].apply(count_main_dishes)
    total_dishes = df["dish_qty"].sum()

    # 4. 區分時段
    lunch_df = df[df["checkout_time"].apply(lambda x: is_in_period(x, "lunch"))]
    dinner_df = df[df["checkout_time"].apply(lambda x: is_in_period(x, "dinner"))]

    df["payment_type"] = df["payment_method"].apply(normalize_payment)

    # 5. 計算指標
    total_orders = len(df)
    total_revenue = df["invoice_amount"].sum()

    peak_hour_series = df.groupby(df["checkout_time"].dt.hour)["dish_qty"].sum()
    top_hours = peak_hour_series.nlargest(2)  # 取前兩名
    first_peak_hour = top_hours.index[0]
    first_peak_hour_dishes = top_hours.iloc[0]
    first_peak_ratio = first_peak_hour_dishes / total_dishes if total_dishes else 0
    second_peak_hour = top_hours.index[1]
    second_peak_hour_dishes = top_hours.iloc[1]
    second_peak_ratio = second_peak_hour_dishes / total_dishes if total_dishes else 0

    # 蛋白質碗數統計（關鍵字 + 碗）
    protein_bowls = {
        protein: int(df["items_text"].apply(lambda text: count_protein_bowls(text, protein)).sum())
        for protein in PROTEIN_RULES
    }

    protein_series = pd.Series(protein_bowls)
    top_proteins = protein_series.sort_values(ascending=False).head(2)

    first_protein = top_proteins.index[0] if len(top_proteins) >= 1 else None
    first_protein_bowls = int(top_proteins.iloc[0]) if len(top_proteins) >= 1 else 0
    first_protein_ratio = first_protein_bowls / total_dishes if total_dishes else 0

    second_protein = top_proteins.index[1] if len(top_proteins) >= 2 else None
    second_protein_bowls = int(top_proteins.iloc[1]) if len(top_proteins) >= 2 else 0
    second_protein_ratio = second_protein_bowls / total_dishes if total_dishes else 0

    # 這裡建議改用精確匹配或定義映射表
    dine_in_mask = df["order_type"].isin(["Dine In", "內用"])
    takeout_mask = df["order_type"].isin(["Takeout", "外帶", "Delivery", "外送"])
    dine_in_dishes = df[dine_in_mask]["dish_qty"].sum()
    takeout_dishes = df[takeout_mask]["dish_qty"].sum()

    pay_in_cash = df[df["payment_type"].isin(["Cash"])]
    pay_in_LinePay = df[df["payment_type"].isin(["LinePay"])]
    pay_in_cash_order_ratio = pay_in_cash.shape[0] / total_orders
    pay_in_LinePay_order_ratio = pay_in_LinePay.shape[0] / total_orders

    cloud_kitchen_orders = df[df["order_source"].isin(["Online Store"])].shape[0]
    cloud_kitchen_ratio = cloud_kitchen_orders / total_orders

    return {
        "date": target_date,
        "metrics": {
            "revenue": round(total_revenue, 2),
            "unit": "dish",
            "total_orders": total_orders,
            "total_dishes": int(total_dishes),
            "avg_dish_price": round(total_revenue / total_dishes, 2) if total_dishes else 0,
            "dine_in_dishes": dine_in_dishes,
            "takeout_dishes": takeout_dishes,
            "cloud_kitchen_orders": cloud_kitchen_orders,
            "cloud_kitchen_ratio": '{:.2f}%'.format(cloud_kitchen_ratio * 100),
        },
        "periods": {
            "lunch_dishes": int(lunch_df["dish_qty"].sum()),
            "dinner_dishes": int(dinner_df["dish_qty"].sum()),
        },
        "operational": {
            "first_peak_hour": f"{first_peak_hour}:00-{first_peak_hour+1}:00",
            "first_peak_hour_dishes": int(first_peak_hour_dishes) if not peak_hour_series.empty else 0,
            "first_peak_hour_ratio": round(first_peak_ratio, 2),
            "second_peak_hour": f"{second_peak_hour}:00-{second_peak_hour+1}:00",
            "second_peak_hour_dishes": int(second_peak_hour_dishes) if not peak_hour_series.empty else 0,
            "second_peak_hour_ratio": round(second_peak_ratio, 2),
            "protein_bowls": protein_bowls,
            "first_protein": first_protein,
            "first_protein_bowls": first_protein_bowls,
            "first_protein_ratio": round(first_protein_ratio, 2),
            "second_protein": second_protein,
            "second_protein_bowls": second_protein_bowls,
            "second_protein_ratio": round(second_protein_ratio, 2),
        },
        "payments": {
            "pay_in_cash_order_ratio": round(pay_in_cash_order_ratio, 2),
            "pay_in_LinePay_order_ratio": round(pay_in_LinePay_order_ratio, 2),
        },
        "assumptions": {
            "employee_meal_rule": "invoice_amount == 0",
            "main_dish_rule": "item name contains '碗' and not in exclude list",
            "voided_rule": "order_status contains 'Voided'",
            "business_hours_applied": BUSINESS_HOURS,
            "protein_rule": "(雞胸肉|豆腐|鮮蝦|鮭魚|鮪魚) + 碗",
        },
    }


from report_renderer import render_daily_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    result = calculate_daily_metrics(args.date)

    if result is None:
        print("No data found for this date.")
    else:
        print(result)
        print(render_daily_report(result))
