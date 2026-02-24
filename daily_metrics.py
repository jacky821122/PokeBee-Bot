import argparse
import pandas as pd
from metrics_common import (
    BUSINESS_HOURS,
    PROTEIN_RULES,
    count_bowls_smart,
    count_protein_bowls,
    is_in_period,
    load_orders,
    normalize_payment,
    preprocess_orders,
)

def calculate_daily_metrics(target_date: str):
    # 優化 1: 增加 Current Status 過濾，避免計入作廢訂單
    # 優化 2: 預先過濾欄位，減少記憶體佔用
    df = load_orders(
        target_date,
        target_date,
        columns=[
            "checkout_time",
            "order_source",
            "order_type",
            "discount_amount",
            "invoice_amount",
            "payment_method",
            "order_status",
            "items_text",
        ],
    )

    if df.empty:
        return None

    # 1. 過濾員工餐與無效訂單
    # 邏輯：排除金額為 0 的訂單（視為員工餐或公關單）
    df = preprocess_orders(df)
    if df.empty:
        return None

    # 2. 時間處理
    df["hour"] = df["checkout_time"].dt.hour

    # 3. 計算碗數 (主餐數)
    df["bowls"] = df["items_text"].apply(count_bowls_smart)
    total_bowls = df["bowls"].sum()

    # 4. 區分時段
    lunch_df = df[df["checkout_time"].apply(lambda x: is_in_period(x, "lunch"))]
    dinner_df = df[df["checkout_time"].apply(lambda x: is_in_period(x, "dinner"))]
    lunch_orders = lunch_df.shape[0]
    dinner_orders = dinner_df.shape[0]

    df["payment_type"] = df["payment_method"].apply(normalize_payment)

    # 5. 計算指標
    total_orders = len(df)
    total_revenue = df["invoice_amount"].sum()

    aov = total_revenue / total_orders if total_orders else 0

    peak_hour_series = df.groupby(df["checkout_time"].dt.hour)["bowls"].sum()
    top_hours = peak_hour_series.nlargest(2)  # 取前兩名
    first_peak_hour = top_hours.index[0] if len(top_hours) >= 1 else None
    first_peak_hour_bowls = top_hours.iloc[0] if len(top_hours) >= 1 else 0
    first_peak_ratio = first_peak_hour_bowls / total_bowls if total_bowls else 0
    second_peak_hour = top_hours.index[1] if len(top_hours) >= 2 else None
    second_peak_hour_bowls = top_hours.iloc[1] if len(top_hours) >= 2 else 0
    second_peak_ratio = second_peak_hour_bowls / total_bowls if total_bowls else 0

    # 蛋白質碗數統計（關鍵字 + 碗）
    protein_bowls = {
        protein: int(df["items_text"].apply(lambda text: count_protein_bowls(text, protein)).sum())
        for protein in PROTEIN_RULES
    }

    protein_series = pd.Series(protein_bowls)
    top_proteins = protein_series.sort_values(ascending=False).head(2)

    first_protein = top_proteins.index[0] if len(top_proteins) >= 1 else None
    first_protein_bowls = int(top_proteins.iloc[0]) if len(top_proteins) >= 1 else 0
    first_protein_ratio = first_protein_bowls / total_bowls if total_bowls else 0

    second_protein = top_proteins.index[1] if len(top_proteins) >= 2 else None
    second_protein_bowls = int(top_proteins.iloc[1]) if len(top_proteins) >= 2 else 0
    second_protein_ratio = second_protein_bowls / total_bowls if total_bowls else 0

    # 這裡建議改用精確匹配或定義映射表
    dine_in_mask = df["order_type"].isin(["Dine In", "內用"])
    takeout_mask = df["order_type"].isin(["Takeout", "外帶", "Delivery", "外送"])
    dine_in_bowls = df[dine_in_mask]["bowls"].sum()
    takeout_bowls = df[takeout_mask]["bowls"].sum()

    pay_in_cash = df[df["payment_type"].isin(["Cash"])]
    pay_in_LinePay = df[df["payment_type"].isin(["LinePay"])]
    pay_in_cash_order_ratio = pay_in_cash.shape[0] / total_orders if total_orders else 0
    pay_in_LinePay_order_ratio = pay_in_LinePay.shape[0] / total_orders if total_orders else 0

    discount_orders = df[df["discount_amount"] > 0].shape[0]
    discount_amount = df["discount_amount"].sum()

    cloud_kitchen_orders = df[df["order_source"].isin(["Online Store"])].shape[0]
    cloud_kitchen_ratio = cloud_kitchen_orders / total_orders if total_orders else 0

    return {
        "date": target_date,
        "metrics": {
            "revenue": round(total_revenue, 2),
            "unit": "bowl",
            "total_orders": total_orders,
            "total_bowls": int(total_bowls),
            "avg_bowl_price": round(total_revenue / total_bowls, 2) if total_bowls else 0,
            "dine_in_bowls": dine_in_bowls,
            "takeout_bowls": takeout_bowls,
            "cloud_kitchen_orders": cloud_kitchen_orders,
            "cloud_kitchen_ratio": '{:.2f}%'.format(cloud_kitchen_ratio * 100),
        },
        "periods": {
            "lunch_bowls": int(lunch_df["bowls"].sum()),
            "dinner_bowls": int(dinner_df["bowls"].sum()),
        },
        "operational": {
            "first_peak_hour": f"{first_peak_hour}:00-{first_peak_hour+1}:00" if first_peak_hour is not None else "--",
            "first_peak_hour_bowls": int(first_peak_hour_bowls) if first_peak_hour is not None else 0,
            "first_peak_hour_ratio": round(first_peak_ratio, 2),
            "second_peak_hour": f"{second_peak_hour}:00-{second_peak_hour+1}:00" if second_peak_hour is not None else "--",
            "second_peak_hour_bowls": int(second_peak_hour_bowls) if second_peak_hour is not None else 0,
            "second_peak_hour_ratio": round(second_peak_ratio, 2),
            "protein_bowls": protein_series.sort_values(ascending=False).to_dict(),
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
            "bowl_rule": "item name contains '碗' and not in exclude list",
            "voided_rule": "order_status contains 'Voided'",
            "business_hours_applied": BUSINESS_HOURS
        }
    }

if __name__ == "__main__":
    from report_renderer import render_daily_report
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    result = calculate_daily_metrics(args.date)

    if result is None:
        print("No data found for this date.")
    else:
        print(result)
        print(render_daily_report(result))
