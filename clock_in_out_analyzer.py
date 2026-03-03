from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

FULL_TIME_NAMES = {"小王叭"}
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class Event:
    kind: str
    timestamp: Optional[datetime] = None


@dataclass
class PairRecord:
    employee: str
    date: str
    shift: str
    in_raw: str
    in_norm: str
    out_raw: str
    out_norm: str
    normal_hours: float
    overtime_hours: float
    note: str


@dataclass
class EmployeeSummary:
    employee: str
    is_full_time: bool
    normal_hours: float = 0.0
    overtime_hours: float = 0.0
    specials: list[str] = None

    def __post_init__(self) -> None:
        if self.specials is None:
            self.specials = []


def round_to_half_hour(dt: datetime) -> datetime:
    m = dt.minute
    if m < 15:
        return dt.replace(minute=0, second=0, microsecond=0)
    if m < 45:
        return dt.replace(minute=30, second=0, microsecond=0)
    return (dt + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


def fmt_hours(hours: float) -> str:
    if abs(hours - round(hours)) < 1e-9:
        return f"{int(round(hours))}"
    return f"{hours:.1f}".rstrip("0").rstrip(".")


def parse_csv(path: Path) -> dict[str, list[Event]]:
    employees: dict[str, list[Event]] = {}
    current_name: Optional[str] = None
    pending_no_in = False

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            c0 = (row[0] or "").strip()
            c1 = (row[1] if len(row) > 1 else "").strip()

            if c0 == "" and c1 == "":
                continue

            if c1 == "" and c0 not in {
                "clock-in",
                "clock-out",
                "no clock-in record",
                "no clock-out record",
            } and not c0.startswith("Total hours"):
                current_name = c0
                employees.setdefault(current_name, [])
                pending_no_in = False
                continue

            if current_name is None:
                continue

            if c0.startswith("Total hours"):
                current_name = None
                pending_no_in = False
                continue

            if c0 == "clock-in" and c1:
                employees[current_name].append(Event("clock-in", datetime.strptime(c1, TIME_FORMAT)))
                continue

            if c0 == "clock-out" and c1:
                kind = "clock-out-no-in" if pending_no_in else "clock-out"
                employees[current_name].append(Event(kind, datetime.strptime(c1, TIME_FORMAT)))
                pending_no_in = False
                continue

            if c0 == "no clock-in record":
                pending_no_in = True
                continue

            if c0 == "no clock-out record":
                employees[current_name].append(Event("no-clock-out"))
                continue

    return {k: v for k, v in employees.items() if v}


def classify_shift(norm_in: datetime) -> tuple[str, datetime]:
    d = norm_in.date()
    h = norm_in.hour + norm_in.minute / 60
    if h < 14:
        return "早班", datetime(d.year, d.month, d.day, 14, 0)
    if h <= 16:
        return "晚班1", datetime(d.year, d.month, d.day, 20, 0)
    return "晚班2", datetime(d.year, d.month, d.day, 20, 30)


def add_record(records: list[PairRecord], summary: EmployeeSummary, rec: PairRecord, force_special: bool = False) -> None:
    records.append(rec)
    summary.normal_hours += rec.normal_hours
    summary.overtime_hours += rec.overtime_hours
    if force_special or rec.note:
        summary.specials.append(f"{rec.date} {rec.note}")


def analyze_employee(name: str, events: list[Event], records: list[PairRecord]) -> EmployeeSummary:
    summary = EmployeeSummary(employee=name, is_full_time=name in FULL_TIME_NAMES)
    current_in: Optional[datetime] = None

    def consume_pair(in_ts: Optional[datetime], out_ts: Optional[datetime], inferred_no_in: bool = False) -> None:
        if summary.is_full_time:
            handle_full_time(summary, records, name, in_ts, out_ts, inferred_no_in)
        else:
            handle_hourly(summary, records, name, in_ts, out_ts, inferred_no_in)

    i = 0
    while i < len(events):
        e = events[i]
        if e.kind == "clock-in":
            if current_in is not None:
                # duplicated clock-in if very close
                if e.timestamp and abs((e.timestamp - current_in).total_seconds()) <= 60:
                    d = current_in.date().isoformat()
                    summary.specials.append(f"{d} 重複 clock-in（<=60秒），丟棄後者")
                    i += 1
                    continue
                consume_pair(current_in, None)
            current_in = e.timestamp

        elif e.kind == "clock-out":
            if current_in is None:
                consume_pair(None, e.timestamp, inferred_no_in=True)
            else:
                consume_pair(current_in, e.timestamp)
                current_in = None

        elif e.kind == "clock-out-no-in":
            consume_pair(None, e.timestamp, inferred_no_in=True)

        elif e.kind == "no-clock-out":
            if current_in is not None:
                consume_pair(current_in, None)
                current_in = None

        i += 1

    if current_in is not None:
        consume_pair(current_in, None)

    return summary


def handle_full_time(summary: EmployeeSummary, records: list[PairRecord], name: str, in_ts: Optional[datetime], out_ts: Optional[datetime], inferred_no_in: bool) -> None:
    date = (in_ts or out_ts).date().isoformat()
    in_norm = round_to_half_hour(in_ts) if in_ts else None
    out_norm = round_to_half_hour(out_ts) if out_ts else None
    normal = 8.0 if (in_ts and out_ts) else 0.0
    overtime = 0.0
    note_parts: list[str] = []

    if not in_ts or not out_ts or inferred_no_in:
        note_parts.append("缺打卡，需人工確認")
    else:
        threshold = out_norm.replace(hour=20, minute=30)
        if out_norm > threshold:
            normal_end = out_norm.replace(hour=20, minute=0)
            overtime = (out_norm - normal_end).total_seconds() / 3600
            note_parts.append(f"下班 {out_norm.strftime('%H:%M')}，計為 {fmt_hours(overtime)} 小時加班")

    rec = PairRecord(
        employee=name,
        date=date,
        shift="正職",
        in_raw=in_ts.strftime(TIME_FORMAT) if in_ts else "",
        in_norm=in_norm.strftime("%Y-%m-%d %H:%M") if in_norm else "",
        out_raw=out_ts.strftime(TIME_FORMAT) if out_ts else "",
        out_norm=out_norm.strftime("%Y-%m-%d %H:%M") if out_norm else "",
        normal_hours=normal,
        overtime_hours=overtime,
        note="；".join(note_parts),
    )
    add_record(records, summary, rec, force_special=bool(note_parts))


def handle_hourly(summary: EmployeeSummary, records: list[PairRecord], name: str, in_ts: Optional[datetime], out_ts: Optional[datetime], inferred_no_in: bool) -> None:
    date = (in_ts or out_ts).date().isoformat()
    in_norm = round_to_half_hour(in_ts) if in_ts else None
    out_norm = round_to_half_hour(out_ts) if out_ts else None

    normal = 0.0
    overtime = 0.0
    note_parts: list[str] = []
    shift = "未知"

    if in_norm and out_norm and in_norm < in_norm.replace(hour=14, minute=0) and out_norm >= out_norm.replace(hour=20, minute=0):
        shift = "全日連續班"
        normal = 8.0
        late_end = out_norm.replace(hour=20, minute=30)
        if out_norm > late_end:
            overtime = (out_norm - late_end).total_seconds() / 3600
        note_parts.append(f"全日連續班（強制拆分），計為 {fmt_hours(normal)} 小時")
        if overtime > 0:
            note_parts.append(f"加班 {fmt_hours(overtime)} 小時")
    elif in_norm and out_norm:
        shift, normal_end = classify_shift(in_norm)
        worked_hours = (out_norm - in_norm).total_seconds() / 3600
        normal = min(worked_hours, 4.0)
        if out_norm - normal_end >= timedelta(minutes=30):
            normal = (normal_end - in_norm).total_seconds() / 3600
            overtime = (out_norm - normal_end).total_seconds() / 3600
            note_parts.append(f"{shift}，加班 {fmt_hours(overtime)} 小時")
        if abs(normal - 4.0) > 1e-9:
            note_parts.append(f"{shift}，正常時數 {fmt_hours(normal)} 小時（非 4 小時）")
    elif in_norm and not out_norm:
        shift, _ = classify_shift(in_norm)
        normal = 4.0
        note_parts.append(f"{shift}，無下班紀錄，計為 4 小時（default）")
    elif out_norm and not in_norm:
        if out_norm.hour < 15 or (out_norm.hour == 14 and out_norm.minute <= 30):
            shift = "早班"
        elif out_norm.hour >= 20:
            shift = "晚班"
        else:
            shift = "未知"
        normal = 4.0
        note_parts.append(f"{shift}，無上班紀錄，推算計為 4 小時")

    rec = PairRecord(
        employee=name,
        date=date,
        shift=shift,
        in_raw=in_ts.strftime(TIME_FORMAT) if in_ts else "",
        in_norm=in_norm.strftime("%Y-%m-%d %H:%M") if in_norm else "",
        out_raw=out_ts.strftime(TIME_FORMAT) if out_ts else "",
        out_norm=out_norm.strftime("%Y-%m-%d %H:%M") if out_norm else "",
        normal_hours=max(normal, 0.0),
        overtime_hours=max(overtime, 0.0),
        note="；".join(note_parts),
    )
    add_record(records, summary, rec, force_special=bool(note_parts) or inferred_no_in)


def extract_month_key(path: Path) -> str:
    m = re.search(r"(\d{4}-\d{2})-\d{2}~\d{4}-\d{2}-\d{2}", path.name)
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m")


def print_summary(summaries: list[EmployeeSummary]) -> None:
    for s in summaries:
        role = "正職" if s.is_full_time else "計時"
        print(f"{s.employee}（{role}）:")
        print(f"正常時數 {fmt_hours(s.normal_hours)} 小時")
        print(f"加班時數 {fmt_hours(s.overtime_hours)} 小時")
        print("特殊班別:")
        if s.specials:
            for line in s.specials:
                print(f"  {line}")
        else:
            print("  無")
        print()


def write_report(records: list[PairRecord], month_key: str) -> Path:
    out_dir = Path("data/clock_in_out")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"clock_report_{month_key}.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["員工", "班別", "日期", "上班原始", "上班normalized", "下班原始", "下班normalized", "正常時數", "加班時數", "備註"])
        for r in records:
            w.writerow([
                r.employee,
                r.shift,
                r.date,
                r.in_raw,
                r.in_norm,
                r.out_raw,
                r.out_norm,
                fmt_hours(r.normal_hours),
                fmt_hours(r.overtime_hours),
                r.note,
            ])
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze iCHEF clock-in/out CSV")
    parser.add_argument("csv_path", help="Path to iCHEF clock-in/out CSV")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    employees = parse_csv(csv_path)
    records: list[PairRecord] = []
    summaries: list[EmployeeSummary] = []

    for name, events in employees.items():
        summary = analyze_employee(name, events, records)
        if summary.normal_hours == 0 and summary.overtime_hours == 0 and not summary.specials:
            continue
        summaries.append(summary)

    print_summary(summaries)
    out_path = write_report(records, extract_month_key(csv_path))
    print(f"CSV report generated: {out_path}")


if __name__ == "__main__":
    main()
