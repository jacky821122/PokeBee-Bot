from typing import Dict
from metrics_common import PROTEIN_RULES

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
    total_bowls = metrics.get("total_bowls", 0)
    avg_bowl_price = metrics.get("avg_bowl_price", 0)

    dine_in = metrics.get("dine_in_bowls", 0)
    takeout = metrics.get("takeout_bowls", 0)

    lunch = periods.get("lunch_bowls", 0)
    dinner = periods.get("dinner_bowls", 0)

    first_peak_hour = operational.get("first_peak_hour", "--")
    first_peak_bowls = operational.get("first_peak_hour_bowls", 0)
    first_peak_ratio = operational.get("first_peak_hour_ratio", 0)
    second_peak_hour = operational.get("second_peak_hour", "--")
    second_peak_bowls = operational.get("second_peak_hour_bowls", 0)
    second_peak_ratio = operational.get("second_peak_hour_ratio", 0)

    pay_in_cash_order_ratio = payments.get("pay_in_cash_order_ratio", 0)
    pay_in_LinePay_order_ratio = payments.get("pay_in_LinePay_order_ratio", 0)

    dine_in_pct = _fmt_percent(dine_in, total_bowls)
    takeout_pct = _fmt_percent(takeout, total_bowls)
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
    lines.append(f"・總出碗數：{total_bowls} 碗")
    lines.append(f"・平均單碗收入：{_fmt_currency(avg_bowl_price)}")
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
    lines.append(f"・{first_peak_hour}：{first_peak_bowls} 碗({first_peak_ratio_pct})")
    lines.append(f"・{second_peak_hour}：{second_peak_bowls} 碗({second_peak_ratio_pct})")
    # lines.append(f"・尖峰出碗：{peak_bowls} 碗")
    lines.append("")

    # Payment
    lines.append("💳 支付方式")
    lines.append(f"・現金：{pay_in_cash_order_ratio_pct}")
    lines.append(f"・Line Pay：{pay_in_LinePay_order_ratio_pct}")

    # Footer note
    # lines.append("📌 備註")
    # lines.append("（本報告以「碗數」為主要分析單位）")

    return "\n".join(lines)

def render_weekly_report(data: dict,
                                      ichef_monthly_limit: int = 150) -> str:
    """
    將 calculate_weekly_metrics() 的原始輸出
    轉換為股東週報文字格式
    """

    # === 基本數據 ===
    start_date = data["start_date"]
    end_date = data["end_date"]
    total_orders = data["total_orders"]
    total_bowls = data["total_bowls"]
    total_revenue = data["total_revenue"]

    avg_bowl_price = data["avg_bowl_price"]

    # === 通路 ===
    dine_in = data["dine_in_orders"]
    takeout = data["takeout_orders"]
    online = data["online_orders"]

    ichef_usage_ratio = "{:.2f}".format(round((online / ichef_monthly_limit) * 100, 1) if ichef_monthly_limit else 0)

    # === 支付 ===
    cash = data["cash_orders"]
    linepay = data["linepay_orders"]

    # === 價格 ===
    price_dist = data["price_distribution"]
    orders_ge_200 = data["orders_ge_200"]

    # === 蛋白質（直接使用 ratio 排名）===
    protein_rank_ratio = data["protein_events_ratio"]

    medal = ["🥇 ", "🥈 ", "🥉 "]

    protein_lines = []
    for idx, (protein, ratio) in enumerate(protein_rank_ratio):
        icon = medal[idx] if idx < 3 else ""
        title = PROTEIN_RULES[protein][0]
        amount = data['protein_events_dict'][protein]
        protein_lines.append("{}{} — {} ({:.2f}%)".format(icon, title, amount, ratio))

    protein_block = "\n".join(protein_lines)

    # === 日別 ===
    max_day, max_bowls = data["max_bowl_day"]
    min_day, min_bowls = data["min_bowl_day"]

    # ========================
    # 組裝報告字串
    # ========================

    report = f"""
📊 試營運週報
期間：{start_date} – {end_date}

━━━━━━━━━━━━━━━━━━
一、營運規模

總訂單數：{total_orders}
總營收：${total_revenue:,.0f}
總出碗數：{total_bowls}
平均單碗收入：${avg_bowl_price}

━━━━━━━━━━━━━━━━━━
二、通路結構

內用：{dine_in}
外帶：{takeout}
雲端餐廳(含內用掃碼點餐及外帶)：{online}

iCHEF 每月額度 {ichef_monthly_limit} 單

━━━━━━━━━━━━━━━━━━
三、支付方式

Line Pay：{linepay}
現金：{cash}

━━━━━━━━━━━━━━━━━━
四、蛋白質需求結構

{protein_block}

━━━━━━━━━━━━━━━━━━
五、日別量體

最高出碗日：{max_day}({max_bowls} 碗)
最低出碗日：{min_day}({min_bowls} 碗)
"""

    return report.strip()

