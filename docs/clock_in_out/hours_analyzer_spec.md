# 打卡紀錄分析器計畫

## Context

老闆需要從 iCHEF 匯出的 clock-in/out CSV 自動計算員工出勤時數，取代人工計算。分正職（小王叭）和計時人員兩套規則，輸出包含：各員工正常/加班時數總計、需人工確認的特殊班別列表，以及詳細 CSV 報告（含 normalized 時間）。

---

## 新建檔案

**`clock_in_out_analyzer.py`** — CLI 腳本，`python clock_in_out_analyzer.py <csv_path>`

---

## 演算法設計

### 1. CSV 解析（State Machine）

讀行並分辨：
- `name,,` → 新員工開始
- `clock-in,YYYY-MM-DD HH:MM:SS,` → 打卡進
- `clock-out,YYYY-MM-DD HH:MM:SS,duration` → 打卡出
- `no clock-in record,,` → 標記下一筆 clock-out 無對應 clock-in
- `no clock-out record,,` → 標記上一筆 clock-in 無對應 clock-out
- `Total hours：...,,` → 員工結束（忽略 iCHEF 計算值，用自己的規則）
- `,,` → 空行，跳過

### 2. 時間 Normalize

```
minute < 15   → round down to :00
15 ≤ minute < 45 → round to :30
minute ≥ 45   → round up to next :00 (+1 hour, minute=0)
```

例：09:55 → 10:00、16:07 → 16:00、20:46 → 21:00

### 3. 配對 Clock-in/out

按順序處理事件，維護 `current_in` 狀態：
- `clock-in` 到達：若 `current_in` 已存在且下一事件也是 clock-in（重複打卡），則若時差 ≤ 60 秒視為重複，丟棄後者
- 配對結果可能是：(in+out)、(in+no-out)、(no-in+out)

### 4. 班別判斷（計時人員）

基於 **normalized clock-in** 時間：
- normalized_in < 14:00 → **早班**，正常下班 14:00
- normalized_in ≤ 16:00 AND normalized_in ≥ 14:00 → **晚班1**，正常下班 20:00
- normalized_in > 16:00 → **晚班2**，正常下班 20:30

若 normalized_in < 14:00 AND normalized_out ≥ 20:00（跨越整個工作日）→ **全日連續班**，強制拆分。

### 5. 時數計算規則

#### 計時人員（非小王叭）

| 情況 | 正常時數（per record） | 加班時數 | Flag |
|------|---------|---------|------|
| 完整班（both in/out）| norm_out - norm_in（實際時數） | 0（per record，見日計加班） | 若正常時數 ≠ 4hr |
| 全日連續班（強制拆分）| norm_out - norm_in（實際時數） | 0（per record，見日計加班） | 必定 flag |
| 只有 clock-in（no clock-out）| 4hr（default） | 0 | 必定 flag |
| 只有 clock-out（no clock-in）| 從 norm_out 推算：若 ≤ 14:30 → 早班4hr；≥ 20:00 → 晚班4hr | 0 | 必定 flag |

**日計加班（post-process）**：計算員工每日所有 record 的時數總和。若日總時數 > 8hr → 正常 8hr，超過部分計為加班，並標註。單一班次超過4hr（但日總 ≤ 8hr）不算加班，全部計入正常時數。

#### 正職員工（小王叭）

- 每天固定計 8 小時（不管實際時數，除非缺打卡）
- 觸發條件：norm_out > 20:30（20:30 以後才算加班）
- 加班量：overtime = norm_out - **20:00**（正常下班時間，非 20:30）
- 若缺 clock-in 或 clock-out → flag

### 6. 跳過邏輯

無任何打卡紀錄的員工（如 admin、姵綺、鄭力升、品歆、渝靜）→ 跳過，不出現在輸出中。

---

## 輸出格式

### Console

```
小王叭（正職）:
正常時數 96 小時
加班時數 0.5 小時
特殊班別:
  2026-02-03 下班 21:00，計為 1 小時加班

許凱惟（計時）:
正常時數 XX 小時
加班時數 X 小時
特殊班別:
  2026-02-02 全日連續班（強制拆分），計為 8 小時
  2026-02-07 早班，無下班紀錄，計為 4 小時（default）
  ...
```

### CSV 報告（`data/clock_in_out/clock_report_YYYY-MM.csv`）

Columns：`員工,班別,日期,上班原始,上班normalized,下班原始,下班normalized,正常時數,加班時數,備註`

日期範圍從輸入檔名解析（`2026-02-01~2026-02-28` → `2026-02`），若解析失敗則用當月。

---

## 關鍵邊緣案例（來自真實資料）

| 員工 | 日期 | 狀況 | 處理方式 |
|------|------|------|---------|
| 許凱惟 | 02-02 | 計時，10:00-20:00 連續 | 強制 8hr，flag |
| 許凱惟 | 02-07 | 早班，no clock-out | 4hr default，flag |
| 林孟儒 | 02-05 | 兩次 clock-in 相差 21 秒 | 視為重複，取第一筆，flag |
| 江秉哲 | 02-14 | 早班 no clock-out + 後有晚班 | 早班 4hr flag + 晚班正常計算 |
| 阿姨 | 02-26 | no clock-in + out 14:03 | 推算早班 4hr，flag |
| 陳韋宏 | 02-12 | no clock-in + out 20:35 | 推算晚班 4hr，flag |
| 林孟儒 | 02-07 | 晚班 16:07-20:30 | 晚班1（4hr正常 + 0.5hr加班），flag overtime |

---

## 驗證

1. `python clock_in_out_analyzer.py "data/clock_in_out/Clock-in_out Record_2026-02-01~2026-02-28.csv"`
2. 確認 console 輸出每位有紀錄員工
3. 確認 `data/clock_in_out/clock_report_2026-02.csv` 生成
4. 手動驗證小王叭：14 天 × 8hr = 112hr 正常，2026-02-03（out 21:09 → norm 21:00 > 20:30）= 21:00 - 20:00 = 1hr 加班
5. 手動驗證許凱惟邊緣案例（02-02 全日、02-07 無 clock-out）
6. 確認 normalized 時間欄位正確（09:55 → 10:00 等）
