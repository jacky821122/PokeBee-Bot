from typing import Dict


def _fmt_currency(value) -> str:
    try:
        return f"${int(round(float(value))):,}"
    except Exception:
        return "$0"


def _fmt_percent(part: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{round(part / total * 100)}%"


def render_daily_report(report: Dict) -> str:
    """
    Render daily metrics JSON into a LINE-friendly text report.
    """

    date = report.get("date", "Unknown date")

    metrics = report.get("metrics", {})
    periods = report.get("periods", {})
    operational = report.get("operational", {})
    payments = report.get("payments", {})

    revenue = metrics.get("revenue", 0)
    total_dishes = metrics.get("total_dishes", 0)
    avg_dish_price = metrics.get("avg_dish_price", 0)

    dine_in = metrics.get("dine_in_dishes", 0)
    takeout = metrics.get("takeout_dishes", 0)

    lunch = periods.get("lunch_dishes", 0)
    dinner = periods.get("dinner_dishes", 0)

    first_peak_hour = operational.get("first_peak_hour", "--")
    first_peak_dishes = operational.get("first_peak_hour_dishes", 0)
    first_peak_ratio = operational.get("first_peak_hour_ratio", 0)
    second_peak_hour = operational.get("second_peak_hour", "--")
    second_peak_dishes = operational.get("second_peak_hour_dishes", 0)
    second_peak_ratio = operational.get("second_peak_hour_ratio", 0)

    pay_in_cash_order_ratio = payments.get("pay_in_cash_order_ratio", 0)
    pay_in_LinePay_order_ratio = payments.get("pay_in_LinePay_order_ratio", 0)

    dine_in_pct = _fmt_percent(dine_in, total_dishes)
    takeout_pct = _fmt_percent(takeout, total_dishes)
    first_peak_ratio_pct = f"{round(first_peak_ratio * 100)}%"
    second_peak_ratio_pct = f"{round(second_peak_ratio * 100)}%"
    pay_in_cash_order_ratio_pct = f"{round(pay_in_cash_order_ratio * 100)}%"
    pay_in_LinePay_order_ratio_pct = f"{round(pay_in_LinePay_order_ratio * 100)}%"

    lines = []

    # Header
    lines.append(f"📊 營運快報｜{date}")
    lines.append("")

    # Revenue summary
    lines.append("💰 營收概況")
    lines.append(f"・總營收：{_fmt_currency(revenue)}")
    lines.append(f"・總出碗數：{total_dishes} 碗")
    lines.append(f"・平均單碗收入：{_fmt_currency(avg_dish_price)}")
    lines.append("")

    # Dish structure
    lines.append("🍽 出餐結構")
    lines.append(f"・內用：{dine_in} 碗({dine_in_pct})")
    lines.append(f"・外帶：{takeout} 碗({takeout_pct})")
    lines.append("")

    # Period performance
    lines.append("⏰ 時段表現")
    lines.append(f"・午餐：{lunch} 碗")
    lines.append(f"・晚餐：{dinner} 碗")
    lines.append("")

    # Operational rhythm
    lines.append("🔥 營運節奏")
    lines.append(f"・{first_peak_hour}：{first_peak_dishes} 碗({first_peak_ratio_pct})")
    lines.append(f"・{second_peak_hour}：{second_peak_dishes} 碗({second_peak_ratio_pct})")
    # lines.append(f"・尖峰出碗：{peak_dishes} 碗")
    lines.append("")

    # Payment
    lines.append("💳 支付方式")
    lines.append(f"・現金：{pay_in_cash_order_ratio_pct}")
    lines.append(f"・Line Pay：{pay_in_LinePay_order_ratio_pct}")

    # Footer note
    # lines.append("📌 備註")
    # lines.append("（本報告以「碗數」為主要分析單位）")

    return "\n".join(lines)


