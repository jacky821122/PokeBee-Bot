import pandas as pd
import pytest
from metrics_common import (
    count_bowls,
    count_bowls_smart,
    count_protein_bowls,
    count_protein_non_bowls,
    count_set_meal_proteins,
    infer_quantity_from_price,
    normalize_payment,
    is_in_period,
    validate_bowl_counts,
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


# ---------------------------------------------------------------------------
# infer_quantity_from_price
# ---------------------------------------------------------------------------

class TestInferQuantityFromPrice:
    def test_single_chicken_bowl(self):
        # 160 × 0.9 = 144
        assert infer_quantity_from_price("雞胸肉自選碗", 144.0) == 1

    def test_triple_chicken_bowl(self):
        # 160 × 3 × 0.9 = 432
        assert infer_quantity_from_price("雞胸肉自選碗", 432.0) == 3

    def test_double_chicken_bowl(self):
        # 160 × 2 × 0.9 = 288
        assert infer_quantity_from_price("雞胸肉自選碗", 288.0) == 2

    def test_chicken_with_addon(self):
        # 216 不是 160 的整數倍 → 算 1 碗（有加購）
        assert infer_quantity_from_price("雞胸肉自選碗", 216.0) == 1

    def test_single_shrimp_bowl(self):
        # 170 × 0.9 = 153
        assert infer_quantity_from_price("鮮蝦自選碗", 153.0) == 1

    def test_double_shrimp_bowl(self):
        # 170 × 2 × 0.9 = 306
        assert infer_quantity_from_price("鮮蝦自選碗", 306.0) == 2

    def test_shrimp_with_addon(self):
        # 225 不是 170 的整數倍 → 算 1 碗（有加購）
        assert infer_quantity_from_price("鮮蝦自選碗", 225.0) == 1

    def test_shrimp_double_with_same_addon(self):
        # (170 + 15) × 2 × 0.9 = 333
        assert infer_quantity_from_price("鮮蝦自選碗", 333.0) == 2

    def test_chicken_single_with_large_addons(self):
        # (160 + 50 + 70 + 80) × 0.9 = 324
        assert infer_quantity_from_price("雞胸肉自選碗", 324.0) == 1

    def test_unknown_bowl(self):
        # 未知品項 → 算 1 碗
        assert infer_quantity_from_price("神秘碗", 999.0) == 1

    def test_set_meal_single(self):
        # 高蛋白健身碗 220 × 0.9 = 198
        assert infer_quantity_from_price("高蛋白健身碗", 198.0) == 1

    def test_set_meal_double(self):
        # 高蛋白健身碗 220 × 2 × 0.9 = 396
        assert infer_quantity_from_price("高蛋白健身碗", 396.0) == 2


# ---------------------------------------------------------------------------
# count_bowls_smart
# ---------------------------------------------------------------------------

class TestCountBowlsSmart:
    def test_single_bowl(self):
        assert count_bowls_smart("雞胸肉自選碗 $144.0") == 1

    def test_triple_chicken_bowl(self):
        # 實際案例：3 碗雞胸肉被合併成一個項目
        assert count_bowls_smart("雞胸肉自選碗 $432.0") == 3

    def test_mixed_bowls_with_triple(self):
        # 實際案例：#-00000447
        items = "鮮蝦自選碗 $225.0,嚴選生鮭魚自選碗 $261.0,雞胸肉自選碗 $432.0,雞胸肉自選碗 $216.0"
        # 1 + 1 + 3 + 1 = 6
        assert count_bowls_smart(items) == 6

    def test_double_bowl(self):
        assert count_bowls_smart("雞胸肉自選碗 $288.0") == 2

    def test_bowl_with_addon(self):
        # 有加購的碗算 1 碗
        assert count_bowls_smart("雞胸肉自選碗 $216.0") == 1

    def test_bag_excluded(self):
        assert count_bowls_smart("雞胸肉自選碗 $144.0, 提袋 $2.0") == 1

    def test_no_price_info(self):
        # 沒有價格資訊，算 1 碗
        assert count_bowls_smart("雞胸肉自選碗") == 1

    def test_empty_string(self):
        assert count_bowls_smart("") == 0

    def test_none_input(self):
        assert count_bowls_smart(None) == 0


# ---------------------------------------------------------------------------
# validate_bowl_counts
# ---------------------------------------------------------------------------

class TestValidateBowlCounts:
    def test_valid_counts(self, capsys):
        # 總碗數與分類相符，不應有警告
        validate_bowl_counts(
            total_bowls=10,
            protein_bowls={"chicken": 5, "salmon": 3, "tofu": 2},
            protein_set_meals={"chicken": 0, "salmon": 0, "tofu": 0}
        )
        captured = capsys.readouterr()
        assert "⚠️" not in captured.out

    def test_small_diff_no_warning(self, capsys):
        # 小誤差（≤5）不應警告
        validate_bowl_counts(
            total_bowls=10,
            protein_bowls={"chicken": 5, "salmon": 2},
            protein_set_meals={"chicken": 0, "salmon": 0}
        )
        captured = capsys.readouterr()
        assert "⚠️" not in captured.out

    def test_large_diff_warning(self, capsys):
        # 大誤差（>5）應該警告
        validate_bowl_counts(
            total_bowls=20,
            protein_bowls={"chicken": 5, "salmon": 2},
            protein_set_meals={"chicken": 0, "salmon": 0}
        )
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "碗數統計異常" in captured.out
