# Plan: 自建打卡 PWA + Google Sheet 後端（整合補登）

## Context

目前打卡走 iCHEF，月底人工下載 CSV 餵給 `clock_in_out_analyzer.py`；補登則靠 LINE 記事本手動記錄。兩套資料分開對照很麻煩。

本計畫的主要 motivation 是**整合打卡與補登到同一張 Google Sheet**，並順便把分析自動化（員工一打卡，analyzer 立刻把結果寫進 sheet）。

產品定位：
- 部署在店內 iPad，登入管理者 Google 帳號常駐不登出
- 員工自助打卡（點名字 + PIN）
- 補登走同一個 PWA 介面的另一個 tab，所有申請都是 raw 資料，月底人工審核
- 不取代現有 iCHEF analyzer（CSV 匯入路徑保留作為備援/對照）

## 可行性結論

**可行**。技術組合成熟（Flask + gspread + PWA），analyzer 核心邏輯不必重寫，以「存 raw punch、每筆觸發當天重算」的方式完整復用。

---

## 架構

```
iPad Safari (PWA, 常駐管理者 Google session)
        │  HTTPS
        ▼
Flask server（pokebee 專案既有的 Flask）
        │  gspread (service account)
        ▼
Google Sheet「pokebee-clock-YYYY」
   ├─ employees        (員工名單 + hashed PIN + role)
   ├─ raw_punches      (每一次打卡原始事件)
   ├─ amendments       (補登申請)
   ├─ analyzed_YYYY-MM (對應現有 XLSX 明細)
   └─ summary_YYYY-MM  (對應現有 XLSX 摘要)
```

**關鍵設計：PWA 永遠走 server，不直連 Google Sheet。** Service account credential 只留在 server 端，iPad 上即使被偷看 URL 也只拿到前端 HTML。

---

## 主要模組與檔案

### 新增
- `clock_pwa/app.py` — Flask blueprint，掛在既有 `line_bot_app.py` 或獨立 port
  - `GET /clock` — PWA 主頁
  - `GET /api/employees` — 員工列表（for 選單）
  - `POST /api/punch` — 打卡：`{employee, pin}` → 自動判斷 in/out → 寫 `raw_punches` → 觸發當日重算
  - `POST /api/amend` — 補登：`{employee, pin, date, shift, in_time, out_time, reason}` → 寫 `amendments`
- `clock_pwa/static/` — PWA 前端（`index.html`, `manifest.json`, `sw.js`, `app.js`, `app.css`）
  - 兩個 tab：「打卡」「補登」
  - 打卡 tab：員工格狀按鈕 → PIN 輸入 → 單一「打卡」按鈕（server 自動判 in/out）
- `clock_pwa/sheets_client.py` — gspread wrapper，封裝讀寫與 schema
- `clock_pwa/analyzer_bridge.py` — 從 `raw_punches` 讀某員工某天 events → 餵給既有 `analyze_employee()` → 寫回 `analyzed_YYYY-MM` / `summary_YYYY-MM`

### 需小幅重構
- `clock_in_out_analyzer.py:88` `parse_csv()` 目前把 CSV 直接轉成 `dict[name, list[Event]]`。抽出一個 `events_from_rows(rows)` 之類的 helper，讓 `analyzer_bridge` 可以用 sheet 讀來的 rows 走同一條路徑。
- `analyze_employee()` (line 279) 維持不動，仍吃 `list[Event]`，**完整復用**。
- `apply_daily_overtime_for_pt()` (line 245) 天然支援單天重算（它本來就按 date group）。

### 重算策略（關鍵）

每次 `/api/punch` 或 `/api/amend` 寫入後：
1. 從 `raw_punches` 讀該員工**該月**全部 events（PT 跨天的 no-clock-out 邊界情況要整月才穩，但實務上算當月就夠）
2. 呼叫 `analyze_employee(name, events)` → 得到 records + summary
3. 刪掉 `analyzed_YYYY-MM` 中該員工的所有 row，寫回新算出來的 records
4. 更新 `summary_YYYY-MM` 該員工那一組

低頻場景（一天幾十次打卡）完全撐得住 Google Sheets API quota。

---

## Schema

### `employees`
| name | pin_hash | role | active |
|---|---|---|---|
| 小王叭 | sha256(...) | full_time | TRUE |
| ... | ... | PT | TRUE |

### `raw_punches`
| id | employee | client_ts | server_ts | source |
|---|---|---|---|---|
| uuid | 小王叭 | 2026-04-16 09:02:11 | 2026-04-16 09:02:12 | pwa |

**不存 in/out 欄位**。由 analyzer 從序列推斷，與 iCHEF CSV 完全對稱（iCHEF 也是交錯的 clock-in/clock-out 事件）。

### `amendments`
| id | submitted_at | employee | date | shift | in_time | out_time | reason | status |
|---|---|---|---|---|---|---|---|---|
| uuid | 2026-04-16 21:00 | 小明 | 2026-04-15 | 早班 | 11:00 | 14:30 | 忘記打卡 | pending |

月底人工把 `status` 改成 `approved`，審核後才手動調整 raw_punches 或直接反映在薪資計算上。**補登不自動影響 analyzer 結果**，只是資料蒐集。

### `analyzed_YYYY-MM` / `summary_YYYY-MM`
欄位直接對齊 `clock_in_out_analyzer.py:402` 的 `明細` headers 與 `format_summary()` 輸出，方便月底一眼對照。

---

## 安全 / 權限

- iPad 維持管理者 Google session 登入（主要屏障）
- 後端僅允許特定 origin
- PIN 以 bcrypt/sha256 儲存，不存明文
- Flask 端把 `/clock` 與 `/api/*` 的路由可選加 shared secret header（與 iPad 綁定），作為 URL 外洩的第二道防線（optional）

---

## 部署注意

- `requirements.txt` + `environment.yml` 同步新增：`gspread`, `google-auth`
- Service account JSON 放 `~/.config/pokebee/gsheet_sa.json`，不進 repo
- Google Sheet 要手動 share 給 service account email
- 既有 `clock_in_out/` CLI 流程保留不動，作為 iCHEF CSV 的備援入口

---

## 驗證方法

1. **單元**：新增 `tests/test_analyzer_bridge.py`，給定模擬 sheet rows，驗證輸出與 `analyze_csv()` 對同一份資料產出一致結果（output parity，符合 CLAUDE.md 規範）
2. **整合**：建測試用 Google Sheet，跑 `POST /api/punch` 幾輪，檢查三張表狀態
3. **手動**：iPad Safari 開 PWA → 加到主畫面 → 模擬一天員工打卡流程
4. **補登**：送補登 → 檢查 `amendments` tab 有紀錄、不影響 `analyzed_*`

---

## 仍待確認

- 後端要獨立 process 還是掛在 `line_bot_app.py` 同一 Flask app？
- 分析結果要不要也 push LINE 通知給管理者？（MVP 不做）
- PWA offline 模式？（MVP 不做，只做 install-to-home）
- 月份切換時（跨月第一次打卡）要自動建新 tab 還是預先建？
