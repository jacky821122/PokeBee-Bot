import argparse

from metrics_common import (
    count_main_dishes,
    is_in_period,
    load_orders,
    normalize_payment,
    preprocess_orders,
)


def is_peak(hour_float: float) -> bool:
    return 12 <= hour_float < 13.5


def calculate_weekly_metrics(start_date: str, end_date: str):
    df = load_orders(
        start_date,
        end_date,
        columns=[
            "checkout_time",
            "order_source",
            "order_type",
            "invoice_amount",
            "payment_method",
            "order_status",
            "items_text",
        ],
    )

    if df.empty:
        return None

    # ---------- 基本前處理 ----------
    # 1. 過濾員工餐與無效訂單
    # 邏輯：排除金額為 0 的訂單（視為員工餐或公關單）
    df = preprocess_orders(df)
    if df.empty:
        return None

    df["date"] = df["checkout_time"].dt.date
    df["hour"] = df["checkout_time"].dt.hour + df["checkout_time"].dt.minute / 60
    df["bowls"] = df["items_text"].apply(count_main_dishes)
    df["is_peak"] = df["hour"].apply(is_peak)

    # ---------- 基礎量體 ----------
    total_orders = len(df)
    total_bowls = df["bowls"].sum()
    total_revenue = df["invoice_amount"].sum()

    # ---------- 訂單 × 碗數結構 ----------
    bowl_dist = {
        "1_bowl_orders": len(df[df["bowls"] == 1]),
        "2_bowl_orders": len(df[df["bowls"] == 2]),
        "3plus_bowl_orders": len(df[df["bowls"] >= 3]),
    }

    bowl_revenue = {
        "1_bowl_revenue": df[df["bowls"] == 1]["invoice_amount"].sum(),
        "2_bowl_revenue": df[df["bowls"] == 2]["invoice_amount"].sum(),
        "3plus_bowl_revenue": df[df["bowls"] >= 3]["invoice_amount"].sum(),
    }

    # ---------- 時段切片 ----------
    hourly_orders = df.groupby(df["checkout_time"].dt.hour).size().to_dict()
    hourly_bowls = df.groupby(df["checkout_time"].dt.hour)["bowls"].sum().to_dict()

    lunch_df = df[df["checkout_time"].apply(lambda x: is_in_period(x, "lunch"))]
    dinner_df = df[df["checkout_time"].apply(lambda x: is_in_period(x, "dinner"))]
    lunch_orders = len(lunch_df)
    dinner_orders = len(dinner_df)

    peak_orders = len(df[df["is_peak"]])
    non_peak_orders = len(df[~df["is_peak"]])

    # ---------- 訂單型態結構 ----------
    dine_in_orders = len(df[df["order_type"] == "Dine In"])
    takeout_orders = len(df[df["order_type"] == "Takeout"])
    online_orders = len(df[df["order_source"] == "Online Store"])

    dine_in_bowls = df[df["order_type"] == "Dine In"]["bowls"].sum()
    takeout_bowls = df[df["order_type"] == "Takeout"]["bowls"].sum()
    online_bowls = df[df["order_source"] == "Online Store"]["bowls"].sum()

    # ---------- 訂單型態 × 時段 ----------
    def cross_count(cond):
        return len(df[cond])

    peak_dine_in = cross_count((df["is_peak"]) & (df["order_type"] == "Dine In"))
    peak_takeout = cross_count((df["is_peak"]) & (df["order_type"] == "Takeout"))
    peak_online = cross_count((df["is_peak"]) & (df["order_source"] == "Online Store"))

    non_peak_dine_in = cross_count((~df["is_peak"]) & (df["order_type"] == "Dine In"))
    non_peak_takeout = cross_count((~df["is_peak"]) & (df["order_type"] == "Takeout"))
    non_peak_online = cross_count((~df["is_peak"]) & (df["order_source"] == "Online Store"))

    # ---------- 金流結構 ----------
    df["payment_type"] = df["payment_method"].apply(normalize_payment)
    cash_orders = len(df[df["payment_type"].isin(["Cash"])])
    linepay_orders = len(df[df["payment_type"].isin(["LinePay"])])

    peak_cash = len(df[(df["is_peak"]) & (df["payment_type"].isin(["Cash"]))])
    peak_linepay = len(df[(df["is_peak"]) & (df["payment_type"].isin(["LinePay"]))])

    non_peak_cash = len(df[(~df["is_peak"]) & (df["payment_type"].isin(["Cash"]))])
    non_peak_linepay = len(df[(~df["is_peak"]) & (df["payment_type"].isin(["LinePay"]))])

    # ---------- 日別穩定性 ----------
    daily_orders = df.groupby("date").size().to_dict()
    daily_bowls = df.groupby("date")["bowls"].sum().to_dict()
    daily_revenue = df.groupby("date")["invoice_amount"].sum().to_dict()

    max_bowl_day = max(daily_bowls.items(), key=lambda x: x[1])
    min_bowl_day = min(daily_bowls.items(), key=lambda x: x[1])

    # ---------- 高價值訂單 ----------
    price_dist = {
        "lt_150": len(df[df["invoice_amount"] < 150]),
        "150_250": len(df[(df["invoice_amount"] >= 150) & (df["invoice_amount"] <= 250)]),
        "gt_250": len(df[df["invoice_amount"] > 250]),
    }

    high_value_orders = len(df[df["invoice_amount"] >= 200])

    # ---------- 輸出 ----------
    return {
        "total_orders": total_orders,
        "total_bowls": total_bowls,
        "total_revenue": total_revenue,
        **bowl_dist,
        **bowl_revenue,
        "hourly_orders": hourly_orders,
        "hourly_bowls": hourly_bowls,
        "lunch_orders": lunch_orders,
        "dinner_orders": dinner_orders,
        "peak_orders": peak_orders,
        "non_peak_orders": non_peak_orders,
        "dine_in_orders": dine_in_orders,
        "takeout_orders": takeout_orders,
        "online_orders": online_orders,
        "dine_in_bowls": dine_in_bowls,
        "takeout_bowls": takeout_bowls,
        "online_bowls": online_bowls,
        "peak_dine_in": peak_dine_in,
        "peak_takeout": peak_takeout,
        "peak_online": peak_online,
        "non_peak_dine_in": non_peak_dine_in,
        "non_peak_takeout": non_peak_takeout,
        "non_peak_online": non_peak_online,
        "cash_orders": cash_orders,
        "linepay_orders": linepay_orders,
        "peak_cash": peak_cash,
        "peak_linepay": peak_linepay,
        "non_peak_cash": non_peak_cash,
        "non_peak_linepay": non_peak_linepay,
        "daily_orders": daily_orders,
        "daily_bowls": daily_bowls,
        "daily_revenue": daily_revenue,
        "max_bowl_day": max_bowl_day,
        "min_bowl_day": min_bowl_day,
        "price_distribution": price_dist,
        "orders_ge_200": high_value_orders,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    result = calculate_weekly_metrics(args.start, args.end)

    if result is None:
        print("No data found during {} to {}.".format(args.start, args.end))
    else:
        for i, (key, value) in enumerate(result.items(), start=1):
            print(f"{i}. {key}: {value}")
