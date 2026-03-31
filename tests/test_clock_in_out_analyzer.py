"""
Unit tests for clock_in_out_analyzer.py.

Helpers
-------
dt(hm)  – datetime on a fixed date (2026-02-01) with time "HH:MM"
ci/co/coni/nco – shorthand event constructors
"""
from datetime import datetime

import pytest

from clock_in_out_analyzer import (
    Event,
    analyze_employee,
    ceiling_to_half_hour,
    classify_shift,
    normalize_in_time,
    normalize_out_time,
)

DATE = "2026-02-01"


def dt(hm: str) -> datetime:
    return datetime.strptime(f"{DATE} {hm}", "%Y-%m-%d %H:%M")


def ci(hm: str) -> Event:
    return Event("clock-in", dt(hm))


def co(hm: str) -> Event:
    return Event("clock-out", dt(hm))


def coni(hm: str) -> Event:
    """clock-out with no matching clock-in (CSV 'no clock-in record')."""
    return Event("clock-out-no-in", dt(hm))


def nco() -> Event:
    """no-clock-out marker."""
    return Event("no-clock-out")


def run(events, name="員工A", is_full_time=False):
    from clock_in_out_analyzer import FULL_TIME_NAMES, analyze_employee

    original = frozenset(FULL_TIME_NAMES)
    if is_full_time:
        FULL_TIME_NAMES.add(name)
    try:
        records = []
        summary = analyze_employee(name, events, records)
        return summary, records
    finally:
        FULL_TIME_NAMES.discard(name)
        if not is_full_time:
            # restore original state (in case name was already there)
            pass


# ---------------------------------------------------------------------------
# ceiling_to_half_hour
# ---------------------------------------------------------------------------

class TestCeilingToHalfHour:
    def test_low_minute_rounds_to_30(self):
        # 09:11 → 09:30
        assert ceiling_to_half_hour(dt("09:11")) == dt("09:30")

    def test_exactly_30_stays_30(self):
        # 09:30 → 09:30
        assert ceiling_to_half_hour(dt("09:30")) == dt("09:30")

    def test_high_minute_rounds_up_to_next_hour(self):
        # 09:31 → 10:00
        assert ceiling_to_half_hour(dt("09:31")) == dt("10:00")

    def test_59_rounds_up(self):
        # 09:59 → 10:00
        assert ceiling_to_half_hour(dt("09:59")) == dt("10:00")


# ---------------------------------------------------------------------------
# normalize_in_time
# ---------------------------------------------------------------------------

class TestNormalizeInTime:
    """Before 10:00 → ceiling only; at or after 10:00 → standard half-hour round."""

    def test_before_10_low_minute(self):
        # 09:11 → 09:30  (0 < 11 ≤ 30)
        assert normalize_in_time(dt("09:11")) == dt("09:30")

    def test_before_10_high_minute(self):
        # 09:31 → 10:00  (31 > 30)
        assert normalize_in_time(dt("09:31")) == dt("10:00")

    def test_before_10_near_top_of_hour(self):
        # 09:55 → 10:00  (55 > 30)
        assert normalize_in_time(dt("09:55")) == dt("10:00")

    def test_at_10_stays(self):
        # 10:00 → 10:00
        assert normalize_in_time(dt("10:00")) == dt("10:00")

    def test_after_10_round_down(self):
        # 10:07 → 10:00  (minute < 15)
        assert normalize_in_time(dt("10:07")) == dt("10:00")

    def test_after_10_round_to_half(self):
        # 10:20 → 10:30  (15 ≤ minute < 45)
        assert normalize_in_time(dt("10:20")) == dt("10:30")

    def test_after_10_round_up(self):
        # 10:55 → 11:00  (minute ≥ 45)
        assert normalize_in_time(dt("10:55")) == dt("11:00")

    def test_afternoon(self):
        # 16:07 → 16:00
        assert normalize_in_time(dt("16:07")) == dt("16:00")


# ---------------------------------------------------------------------------
# normalize_out_time
# ---------------------------------------------------------------------------

class TestNormalizeOutTime:
    """At/before normal_end → standard round; grace zone → clamp; after → floor."""

    def test_before_normal_end(self):
        # 19:47 with end=20:00 → round(19:47)=20:00
        assert normalize_out_time(dt("19:47"), dt("20:00")) == dt("20:00")

    def test_in_grace_zone(self):
        # 20:17 with end=20:00 → clamped to 20:00
        assert normalize_out_time(dt("20:17"), dt("20:00")) == dt("20:00")

    def test_grace_zone_upper_boundary(self):
        # 20:29 with end=20:00 → still in grace (< 20:30) → 20:00
        assert normalize_out_time(dt("20:29"), dt("20:00")) == dt("20:00")

    def test_after_grace_floors(self):
        # 20:49 with end=20:00 → floor(20:49)=20:30
        assert normalize_out_time(dt("20:49"), dt("20:00")) == dt("20:30")

    def test_late_shift_normal_end_2030(self):
        # 20:29 with end=20:30 → round(20:29)=20:30
        assert normalize_out_time(dt("20:29"), dt("20:30")) == dt("20:30")

    def test_overtime_hour(self):
        # 21:09 with end=20:00 → floor(21:09)=21:00
        assert normalize_out_time(dt("21:09"), dt("20:00")) == dt("21:00")

    def test_no_normal_end_uses_standard_round(self):
        # normal_end=None → round(20:17)=20:30  (minute=17, 15≤17<45)
        assert normalize_out_time(dt("20:17"), None) == dt("20:30")


# ---------------------------------------------------------------------------
# classify_shift
# ---------------------------------------------------------------------------

class TestClassifyShift:
    def test_early_shift(self):
        shift, end = classify_shift(dt("10:00"))
        assert shift == "早班"
        assert (end.hour, end.minute) == (14, 0)

    def test_late_shift_1_at_boundary(self):
        shift, end = classify_shift(dt("14:00"))
        assert shift == "晚班1"
        assert (end.hour, end.minute) == (20, 0)

    def test_late_shift_1_at_1600(self):
        shift, _ = classify_shift(dt("16:00"))
        assert shift == "晚班1"

    def test_late_shift_2(self):
        shift, end = classify_shift(dt("16:30"))
        assert shift == "晚班2"
        assert (end.hour, end.minute) == (20, 30)


# ---------------------------------------------------------------------------
# analyze_employee — 計時人員
# ---------------------------------------------------------------------------

class TestAnalyzeEmployeeHourly:
    """Edge cases based on the spec and real data examples."""

    # --- normal shifts ---

    def test_early_shift_partial_hours(self):
        # in 10:55→11:00, out 13:47→14:00 → 早班 3hr normal
        s, recs = run([ci("10:55"), co("13:47")])
        assert len(recs) == 1
        assert recs[0].shift == "早班"
        assert recs[0].normal_hours == 3.0
        assert recs[0].overtime_hours == 0.0

    def test_early_shift_full_4hr(self):
        # in 10:00→10:00, out 14:02→14:00 (grace) → 早班 4hr
        s, recs = run([ci("10:00"), co("14:02")])
        assert recs[0].normal_hours == 4.0
        assert recs[0].overtime_hours == 0.0

    def test_late_shift_1_past_normal_end_no_overtime(self):
        # 林孟儒 02-07: in 16:07→16:00, out 20:30 → 晚班1, worked 4.5hr
        # Daily total 4.5 < 8hr → all normal, no overtime
        s, recs = run([ci("16:07"), co("20:30")])
        assert recs[0].shift == "晚班1"
        assert recs[0].normal_hours == 4.5
        assert recs[0].overtime_hours == 0.0

    def test_late_shift_2_no_overtime(self):
        # in 16:30→16:30, out 20:30→20:30 (≤ normal_end) → 晚班2 4hr exact
        s, recs = run([ci("16:30"), co("20:30")])
        assert recs[0].shift == "晚班2"
        assert recs[0].normal_hours == 4.0
        assert recs[0].overtime_hours == 0.0

    # --- 全日連續班 ---

    def test_full_day_shift(self):
        # 許凱惟 02-02: in 10:00, out 20:00 → 全日連續班
        # Treated as 4hr + 4hr (forgot to clock out/in during break) → 8 normal
        s, recs = run([ci("10:00"), co("20:00")])
        assert recs[0].shift == "全日連續班"
        assert recs[0].normal_hours == 8.0
        assert recs[0].overtime_hours == 0.0

    def test_full_day_shift_with_overtime(self):
        # in 10:00, out 21:00 → 全日連續班, out_norm 21:00 > 20:30 → 0.5hr overtime
        s, recs = run([ci("10:00"), co("21:00")])
        assert recs[0].shift == "全日連續班"
        assert recs[0].normal_hours == 8.0
        assert recs[0].overtime_hours == 0.5

    # --- 缺打卡 ---

    def test_no_clock_out_defaults_to_4hr(self):
        # 許凱惟 02-07: no clock-out → 4hr default, flagged
        s, recs = run([ci("10:55"), nco()])
        assert recs[0].normal_hours == 4.0
        assert recs[0].overtime_hours == 0.0
        assert "無下班紀錄" in recs[0].note

    def test_no_clock_in_early_infers_early_shift(self):
        # 阿姨 02-26: no clock-in, out 14:03→14:00 → 早班 4hr
        s, recs = run([coni("14:03")])
        assert recs[0].shift == "早班"
        assert recs[0].normal_hours == 4.0

    def test_no_clock_in_late_infers_late_shift(self):
        # 陳韋宏 02-12: no clock-in, out 20:35→20:30 → 晚班 4hr
        s, recs = run([coni("20:35")])
        assert recs[0].shift == "晚班"
        assert recs[0].normal_hours == 4.0

    # --- 重複 clock-in ---

    def test_duplicate_clock_in_within_60s_discards_second(self):
        # 林孟儒 02-05: two clock-ins 21s apart → one pair, second discarded
        t1 = datetime(2026, 2, 5, 10, 55, 2)
        t2 = datetime(2026, 2, 5, 10, 55, 23)   # +21s
        t3 = datetime(2026, 2, 5, 19, 47, 48)
        events = [Event("clock-in", t1), Event("clock-in", t2), Event("clock-out", t3)]
        s, recs = run(events)
        assert len(recs) == 1
        assert recs[0].in_raw == t1.strftime("%Y-%m-%d %H:%M:%S")
        assert any("重複" in sp for sp in s.specials)

    def test_two_clock_ins_over_60s_creates_two_pairs(self):
        # >60s apart → first has no-out, second pairs with clock-out
        t1 = datetime(2026, 2, 5, 10, 0, 0)
        t2 = datetime(2026, 2, 5, 10, 5, 0)    # +5min
        t3 = datetime(2026, 2, 5, 19, 0, 0)
        events = [Event("clock-in", t1), Event("clock-in", t2), Event("clock-out", t3)]
        s, recs = run(events)
        assert len(recs) == 2

    # --- 江秉哲 02-14：早班 no clock-out + 晚班 ---

    def test_early_no_out_then_late_shift(self):
        events = [ci("10:00"), nco(), ci("16:30"), co("20:30")]
        s, recs = run(events)
        assert len(recs) == 2
        early, late = recs[0], recs[1]
        assert early.shift == "早班"
        assert early.normal_hours == 4.0   # default
        assert late.shift == "晚班2"
        assert late.normal_hours == 4.0

    # --- shifted schedule (阿姨模式) ---

    def test_shifted_schedule_no_overtime(self):
        # in 10:30→10:30, out 14:36→14:30 (grace→floor), worked=4.0 → no overtime
        s, recs = run([ci("10:30"), co("14:36")])
        assert recs[0].shift == "早班"
        assert recs[0].normal_hours == 4.0
        assert recs[0].overtime_hours == 0.0

    def test_shifted_schedule_slightly_long_no_overtime(self):
        # in 10:00→10:00, out 14:35→14:30, worked=4.5hr
        # Daily total 4.5 < 8hr → all normal, no overtime
        s, recs = run([ci("10:00"), co("14:35")])
        assert recs[0].shift == "早班"
        assert recs[0].normal_hours == 4.5
        assert recs[0].overtime_hours == 0.0

    # --- summary accumulation ---

    def test_summary_totals_across_pairs(self):
        # two pairs: 3hr + 4hr → total 7hr
        events = [ci("10:55"), co("13:47"), ci("16:30"), co("20:30")]
        s, recs = run(events)
        assert s.normal_hours == 3.0 + 4.0


# ---------------------------------------------------------------------------
# analyze_employee — 正職（小王叭）
# ---------------------------------------------------------------------------

class TestAnalyzeEmployeeFullTime:
    NAME = "小王叭"

    def _run(self, events):
        return run(events, name=self.NAME, is_full_time=True)

    def test_normal_day_counts_8hr(self):
        s, recs = self._run([ci("10:00"), co("20:00")])
        assert recs[0].normal_hours == 8.0
        assert recs[0].overtime_hours == 0.0

    def test_overtime_triggers_at_2030(self):
        # out 20:30 → out_norm=20:30, >= 20:30 → 0.5hr overtime
        s, recs = self._run([ci("10:00"), co("20:30")])
        assert recs[0].normal_hours == 8.0
        assert recs[0].overtime_hours == 0.5

    def test_overtime_before_2030_no_overtime(self):
        # out 20:17 → grace → out_norm=20:00, < 20:30 → no overtime
        s, recs = self._run([ci("10:00"), co("20:17")])
        assert recs[0].overtime_hours == 0.0

    def test_overtime_21_09(self):
        # 小王叭 02-03: out 21:09 → norm 21:00, overtime = 21:00 - 20:00 = 1hr
        s, recs = self._run([ci("10:00"), co("21:09")])
        assert recs[0].normal_hours == 8.0
        assert recs[0].overtime_hours == 1.0

    def test_missing_clock_out_flagged_and_zero_hours(self):
        s, recs = self._run([ci("10:00"), nco()])
        assert "缺下班打卡" in recs[0].note
        assert recs[0].normal_hours == 0.0

    def test_accumulates_across_multiple_days(self):
        # day1: normal 8hr; day2: 8hr + 1hr overtime
        d1 = datetime(2026, 2, 1, 10, 0)
        d2_in = datetime(2026, 2, 2, 10, 0)
        d2_out = datetime(2026, 2, 2, 21, 9)
        events = [
            Event("clock-in", d1),
            Event("clock-out", d1.replace(hour=20)),
            Event("clock-in", d2_in),
            Event("clock-out", d2_out),
        ]
        s, recs = self._run(events)
        assert s.normal_hours == 16.0
        assert s.overtime_hours == 1.0
