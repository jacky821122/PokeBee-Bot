import pytest
from conftest import insert_order
from daily_metrics import calculate_daily_metrics


class TestCalculateDailyMetrics:
    def test_no_data_returns_none(self, db):
        result = calculate_daily_metrics("2099-01-01")
        assert result is None

    def test_basic_metrics(self, db):
        insert_order(db,
            checkout_time="2026-01-15 11:30:00",
            items_text="雞胸肉自選碗 $149.0",
            invoice_amount=149,
            order_type="Dine In",
            payment_method="現金(Cash payment module)",
        )
        insert_order(db,
            checkout_time="2026-01-15 12:00:00",
            items_text="嚴選生鮭魚自選碗 $171.0, 雞胸肉自選碗 $149.0",
            invoice_amount=320,
            order_type="Dine In",
            payment_method="LinePay (未整合)(Custom payment module)",
        )
        insert_order(db,
            checkout_time="2026-01-15 17:00:00",
            items_text="鮮蝦自選碗 $153.0",
            invoice_amount=153,
            order_type="Takeout",
            payment_method="LinePay (未整合)(Custom payment module)",
        )

        result = calculate_daily_metrics("2026-01-15")
        assert result is not None

        metrics = result["metrics"]
        periods = result["periods"]

        assert metrics["total_bowls"] == 4
        assert metrics["revenue"] == 622
        assert metrics["dine_in_bowls"] == 3
        assert metrics["takeout_bowls"] == 1
        assert periods["lunch_bowls"] == 3
        assert periods["dinner_bowls"] == 1

    def test_voided_order_excluded(self, db):
        insert_order(db,
            checkout_time="2026-01-20 12:00:00",
            items_text="雞胸肉自選碗 $149.0",
            invoice_amount=149,
        )
        insert_order(db,
            checkout_time="2026-01-20 13:00:00",
            items_text="嚴選生鮭魚自選碗 $171.0",
            invoice_amount=171,
            order_status="Voided",
        )

        result = calculate_daily_metrics("2026-01-20")
        assert result is not None
        assert result["metrics"]["total_bowls"] == 1

    def test_zero_amount_excluded(self, db):
        insert_order(db,
            checkout_time="2026-01-21 12:00:00",
            items_text="雞胸肉自選碗 $180.0",
            invoice_amount=180,
        )
        insert_order(db,
            checkout_time="2026-01-21 13:00:00",
            items_text="員工餐 $0.0",
            invoice_amount=0,
        )

        result = calculate_daily_metrics("2026-01-21")
        assert result is not None
        assert result["metrics"]["total_orders"] == 1
