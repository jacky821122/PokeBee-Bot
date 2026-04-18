# Plan: Port `clock_in_out_analyzer.py` → TypeScript

## Context

為了讓新專案 `pokebeeClock`（Next.js + Vercel）與分析邏輯 stack 一致，要把現有 Python analyzer 移植到 TypeScript。

**目標**：產出獨立 TS package `../pokebeeClock-analyzer/`，輸出結果逐字等同於 Python 版（output parity），之後搬進 pokebeeClock `src/lib/analyzer/`。

**一次性任務**：port 完 package 使命結束；Python 版留在 pokebee 專案作為 iCHEF CSV CLI 與 ground truth。

## 範圍

### 要 port 的
- `pokebee/clock_in_out_analyzer.py` 的**計算邏輯**：
  - `round_to_half_hour` / `floor_to_half_hour` / `ceiling_to_half_hour`
  - `normalize_in_time` / `normalize_out_time`
  - `classify_shift`（早班 / 晚班1 / 晚班2）
  - `handle_full_time`（正職）
  - `handle_hourly`（計時，包含全日連續班強制拆分、4小時 default、無上班/下班紀錄推算）
  - `apply_daily_overtime_for_pt`（PT 日總時數 > 8 才計加班）
  - `analyze_employee`（事件序列配對 + 重複 clock-in 去重）
  - `fmt_hours`
  - `EmployeeSummary` / `PairRecord` / `Event` 資料結構

### 不 port 的
- CSV 解析（`parse_csv`）— 新系統直接從 Google Sheet 讀結構化 events
- XLSX / CSV 輸出（`write_xlsx_report` / `write_report`）— 新系統寫 Google Sheet
- CLI 入口（`main`）

### API 設計

```typescript
// src/events.ts
export type Event =
  | { kind: 'clock-in'; timestamp: Date }
  | { kind: 'clock-out'; timestamp: Date }
  | { kind: 'clock-out-no-in'; timestamp: Date }
  | { kind: 'no-clock-out' };

// src/analyzer.ts
export interface PairRecord { /* 對齊 Python 版 */ }
export interface EmployeeSummary { /* 對齊 Python 版 */ }

export function analyzeEmployee(
  name: string,
  events: Event[],
  isFullTime: boolean
): { summary: EmployeeSummary; records: PairRecord[] };
```

**重要**：不要把 `FULL_TIME_NAMES` 這個常數硬編到 TS 裡。Python 版的 `FULL_TIME_NAMES = {"小王叭"}` 是暫時的。TS 版要求 caller 傳 `isFullTime` 旗標（從 `employees` sheet 的 role 欄位來）。

## 專案結構

```
pokebeeClock-analyzer/
├─ package.json           (vitest, typescript, tsx — 最小依賴)
├─ tsconfig.json
├─ src/
│  ├─ events.ts
│  ├─ time_utils.ts       (round/floor/ceiling_to_half_hour, normalize_*, fmt_hours)
│  ├─ analyzer.ts         (analyzeEmployee, handle_full_time, handle_hourly, ...)
│  └─ index.ts            (re-exports)
├─ tests/
│  ├─ parity.test.ts      ◄── 核心：用 pokebee 的 tests/fixtures 驗證 TS 輸出 == Python 輸出
│  └─ unit.test.ts        (time_utils 邊界測試)
├─ tests/fixtures/
│  └─ (從 pokebee/tests/fixtures/ 複製, 若無則用 Python 版跑現有 CSV 產出 ground truth)
└─ README.md              (說明：這是 port package，完成後搬進 pokebeeClock)
```

## Parity 測試策略

這是整個 port 最重要的部分，直接對應 pokebee CLAUDE.md 的 output-parity 規則。

**步驟**
1. 從 `pokebee/tests/` 或 `pokebee/data/clock_in_out/raw/` 找幾份實際 iCHEF CSV
2. 跑 Python 版 `analyze_csv()` → 得 `(records, summaries)` → 序列化為 JSON fixture
3. 把同樣的 events 輸入轉成 TS 可讀格式 → 跑 TS `analyzeEmployee()` → 序列化
4. vitest assert 兩邊 JSON 逐字相等

**fixture 設計**
```
tests/fixtures/
├─ case_01_normal_month.py_output.json    (Python 跑出的 ground truth)
├─ case_01_normal_month.events.json       (輸入 events，TS 讀)
├─ case_02_full_day_split.*
├─ case_03_no_clock_out.*
├─ case_04_duplicate_clock_in.*
└─ case_05_pt_daily_overtime.*
```

至少涵蓋以下邊界：
- 正職標準 8 小時
- 正職加班（下班 >= 20:30）
- PT 早班 4 小時整
- PT 晚班1 / 晚班2
- 全日連續班強制拆分
- 無上班紀錄（clock-out-no-in）
- 無下班紀錄（no-clock-out）
- 重複 clock-in（<=60 秒）去重
- PT 日總時數 > 8 觸發加班重分配

## 工作流程

1. Agent 讀 `pokebee/clock_in_out_analyzer.py`（完整）+ `docs/clock_in_out/hours_analyzer_spec.md`
2. Agent 讀 `pokebee/tests/` 看既有 Python 測試結構
3. Agent 在 `../pokebeeClock-analyzer/` 建 scaffold
4. Agent 產生 Python fixture JSON（跑 Python analyzer 把現有 CSV 轉出）
5. Agent port TS 程式碼
6. Agent 寫 parity tests，反覆跑 `npm test` 直到全綠
7. Agent 提交時附上：parity test 通過截圖/log、cover 了哪些 case 的清單

## 交付條件

- [ ] `npm test` 全綠
- [ ] Parity test 至少 cover 前述 9 種邊界
- [ ] `src/index.ts` 匯出穩定 API（`analyzeEmployee`, `EmployeeSummary`, `PairRecord`, `Event`）
- [ ] README.md 說明：API 用法 + 如何跑測試 + 如何搬進 pokebeeClock
- [ ] 無額外執行時依賴（`dependencies: {}`，devDeps only）

## 不要做的事

- ❌ 碰 pokebee 專案任何檔案（只讀不寫）
- ❌ 建 Next.js scaffold（那是 pokebeeClock 的事）
- ❌ 碰 Google Sheets API
- ❌ 硬編 `FULL_TIME_NAMES`
- ❌ 改動演算法（即使覺得可以優化 — 保持 parity 優先）

## 參考檔案路徑

- Source: `/mnt/d/Users/Jacky/SynologyDrive/jacky821122/pokebee/clock_in_out_analyzer.py`
- Spec: `/mnt/d/Users/Jacky/SynologyDrive/jacky821122/pokebee/docs/clock_in_out/hours_analyzer_spec.md`
- Fixtures: `/mnt/d/Users/Jacky/SynologyDrive/jacky821122/pokebee/tests/` 與 `data/clock_in_out/` 下的 CSV
