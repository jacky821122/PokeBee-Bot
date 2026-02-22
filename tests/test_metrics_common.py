import pandas as pd
import pytest
from metrics_common import (
    count_bowls,
    count_protein_bowls,
    count_protein_non_bowls,
    count_set_meal_proteins,
    normalize_payment,
    is_in_period,
    PROTEIN_RULES,
)


# ---------------------------------------------------------------------------
# count_bowls
# ---------------------------------------------------------------------------

class TestCountBowls:
    def test_single_bowl(self):
        assert count_bowls("雞胸肉自選碗 $149.0") == 1

    def test_multiple_bowls(self):
        assert count_bowls("雞胸肉自選碗 $149.0, 嚴選生鮭魚自選碗 $171.0") == 2

    def test_bag_excluded(self):
        assert count_bowls("雞胸肉自選碗 $149.0, 提袋 $2.0") == 1

    def test_addon_prefix_excluded(self):
        assert count_bowls("加購一份雞胸肉碗 $50.0") == 0

    def test_no_bowl_keyword(self):
        assert count_bowls("味噌湯 $30.0") == 0

    def test_empty_string(self):
        assert count_bowls("") == 0

    def test_none_input(self):
        assert count_bowls(None) == 0

    def test_non_string_input(self):
        assert count_bowls(123) == 0


# ---------------------------------------------------------------------------
# count_protein_bowls
# ---------------------------------------------------------------------------

class TestCountProteinBowls:
    def test_chicken_bowl(self):
        assert count_protein_bowls("雞胸肉自選碗 $149.0", "chicken") == 1

    def test_salmon_bowl(self):
        assert count_protein_bowls("嚴選生鮭魚自選碗 $171.0", "salmon") == 1

    def test_wrong_protein(self):
        assert count_protein_bowls("雞胸肉自選碗 $149.0", "salmon") == 0

    def test_protein_without_bowl_keyword(self):
        # 含蛋白質關鍵字但不是碗 → 不計入
        assert count_protein_bowls("雞胸肉 80g $0.0", "chicken") == 0

    def test_set_meal_no_protein_keyword(self):
        # 套餐名稱裡沒有直接的蛋白質關鍵字 → 不計入
        assert count_protein_bowls("海味雙魚碗 $234.0", "salmon") == 0


# ---------------------------------------------------------------------------
# count_protein_non_bowls
# ---------------------------------------------------------------------------

class TestCountProteinNonBowls:
    def test_tofu_addon(self):
        assert count_protein_non_bowls("豆腐 80g $0.0", "tofu") == 1

    def test_salmon_addon(self):
        assert count_protein_non_bowls("嚴選生鮭魚 45g $0.0", "salmon") == 1

    def test_bowl_not_counted(self):
        # 雞胸肉自選碗 是碗 → 不算 non-bowl protein
        assert count_protein_non_bowls("雞胸肉自選碗 $149.0", "chicken") == 0


# ---------------------------------------------------------------------------
# count_set_meal_proteins
# ---------------------------------------------------------------------------

_ALL_PROTEINS = list(PROTEIN_RULES.keys())

def _zeros(**overrides):
    base = {p: 0 for p in _ALL_PROTEINS}
    base.update(overrides)
    return base


class TestCountSetMealProteins:
    def test_high_protein_bowl(self):
        result = count_set_meal_proteins("高蛋白健身碗 $189.0")
        assert result == _zeros(chicken=2)

    def test_double_fish_bowl(self):
        result = count_set_meal_proteins("海味雙魚碗 $234.0")
        assert result == _zeros(salmon=1, tuna=1)

    def test_tofu_bowl(self):
        result = count_set_meal_proteins("清爽佛陀碗 $120.0")
        assert result == _zeros(tofu=1)

    def test_non_set_meal(self):
        result = count_set_meal_proteins("味噌湯 $30.0")
        assert result == _zeros()

    def test_multiple_set_meals(self):
        result = count_set_meal_proteins("高蛋白健身碗 $189.0, 海味雙魚碗 $234.0")
        assert result == _zeros(chicken=2, salmon=1, tuna=1)


# ---------------------------------------------------------------------------
# normalize_payment
# ---------------------------------------------------------------------------

class TestNormalizePayment:
    def test_cash(self):
        assert normalize_payment("現金(Cash payment module)") == "Cash"

    def test_linepay(self):
        assert normalize_payment("LinePay (未整合)(Custom payment module)") == "LinePay"

    def test_none(self):
        assert normalize_payment(None) == "Other"

    def test_unknown_method(self):
        assert normalize_payment("信用卡") == "Other"


# ---------------------------------------------------------------------------
# is_in_period
# ---------------------------------------------------------------------------

def _ts(time_str: str) -> pd.Timestamp:
    return pd.Timestamp(f"2026-01-01 {time_str}")


class TestIsInPeriod:
    # lunch boundary
    def test_lunch_start_inclusive(self):
        assert is_in_period(_ts("11:00"), "lunch") is True

    def test_lunch_midday(self):
        assert is_in_period(_ts("12:30"), "lunch") is True

    def test_lunch_end_inclusive(self):
        assert is_in_period(_ts("14:30"), "lunch") is True

    def test_gap_not_lunch(self):
        assert is_in_period(_ts("15:00"), "lunch") is False

    # dinner boundary
    def test_dinner_start_inclusive(self):
        assert is_in_period(_ts("16:30"), "dinner") is True

    def test_dinner_midpoint(self):
        assert is_in_period(_ts("18:00"), "dinner") is True

    def test_after_dinner_end(self):
        assert is_in_period(_ts("20:01"), "dinner") is False
