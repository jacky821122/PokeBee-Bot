import pandas as pd

import weekly_generator


def test_weekly_protein_events_include_pork_adds(monkeypatch):
    orders = pd.DataFrame(
        [
            {
                "checkout_time": "2026-02-24 12:10:00",
                "order_source": "On site",
                "order_type": "Dine In",
                "invoice_amount": 160,
                "payment_method": "現金(Cash payment module)",
                "order_status": "Issued",
                "items_text": "壽喜燒豬自選碗 $160.0",
            }
        ]
    )
    modifiers = pd.DataFrame([
        {"name": "加購一份壽喜燒豬", "count": 2},
    ])

    monkeypatch.setattr(weekly_generator, "load_orders", lambda *args, **kwargs: orders)
    monkeypatch.setattr(weekly_generator, "load_modifier", lambda *args, **kwargs: modifiers)

    result = weekly_generator.calculate_weekly_metrics("2026-02-22", "2026-02-28")

    assert result is not None

    protein_adds_dict = dict(result["protein_adds"])
    assert protein_adds_dict["pork"] == 2

    assert result["protein_events_dict"]["pork"] == 3

    protein_events_ratio_dict = dict(result["protein_events_ratio"])
    assert protein_events_ratio_dict["pork"] == 100.0
