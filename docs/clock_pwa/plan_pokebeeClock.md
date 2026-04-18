# Plan: pokebeeClock — 自建打卡 + 補登 PWA

## Context

**動機**
1. 現行打卡用 iCHEF CSV，月底人工匯入；補登用 LINE 記事本。兩邊資料分開對照很麻煩
2. 希望**打卡與補登合併到同一張 Google Sheet**，月底一次看完
3. 順便讓打卡分析自動化（打卡即時重算）

**產品定位**
- 店內 iPad 常駐管理者 Google 帳號，員工自助打卡（點名字 + PIN）
- 補登同一 PWA 裡的 tab，月底人工審核（不影響 analyzer 自動結果）
- 不取代現有 iCHEF 流程，pokebee 的 Python analyzer 保留為 ground truth

**架構決定**
- **新專案 `pokebeeClock`**，不混入 pokebee Flask
- **Next.js 16 + Vercel + googleapis**，完全仿 `../pokebeeExpense/app/` 的成功模型
- **analyzer 由 Python port 成 TypeScript**（見 `plan_analyzer_port.md`），讓整個 serving stack 一致

## 技術棧

| | 來源/參考 |
|---|---|
| Framework | Next.js 16 (App Router) — 抄 pokebeeExpense |
| Hosting | Vercel |
| Data store | Google Sheet（單張，多 tab） |
| Sheets client | `googleapis` (service account) — 抄 pokebeeExpense `src/lib/sheets.ts` |
| Styling | Tailwind v4 — 抄 pokebeeExpense |
| PWA | `public/manifest.json` + service worker — 抄 pokebeeExpense `public/` |
| Auth (admin) | `Authorization: Bearer $ADMIN_SECRET` — 抄 pokebeeExpense 的 STATS_SECRET 模式 |
| Analyzer | 由 `pokebeeClock-analyzer` port 專案提供（port 完搬進 `src/lib/analyzer/`） |

## Google Sheet 結構（單張 spreadsheet，多 sheet）

### `employees`
| name | pin_hash | role | active |
|---|---|---|---|
| 小王叭 | sha256(...) | full_time | TRUE |

### `raw_punches`（打卡原始事件）
| id | employee | client_ts | server_ts | source |
|---|---|---|---|---|
| uuid | 小王叭 | 2026-04-16 09:02:11 | 2026-04-16 09:02:12 | pwa |

**不存 in/out 欄位** — 交給 analyzer 從序列推斷，與 iCHEF CSV 的 events 對稱。

### `amendments`（補登申請）
| id | submitted_at | employee | date | shift | in_time | out_time | reason | status |
|---|---|---|---|---|---|---|---|---|
| uuid | 2026-04-16 21:00 | 小明 | 2026-04-15 | 早班 | 11:00 | 14:30 | 忘記打卡 | pending |

月底人工把 `status` 改成 `approved`。**補登不自動影響 analyzer 結果**，只是蒐集。

### `analyzed_YYYY-MM` / `summary_YYYY-MM`
欄位對齊 Python analyzer 的 XLSX 明細 headers 與 `format_summary()` 輸出（見 pokebee `clock_in_out_analyzer.py:402`）。

## 專案結構（仿 pokebeeExpense）

```
pokebeeClock/
├─ app/                              (Next.js 本體)
│  ├─ src/
│  │  ├─ app/
│  │  │  ├─ page.tsx                 (打卡主頁: 員工格 + PIN)
│  │  │  ├─ amend/page.tsx           (補登表單)
│  │  │  ├─ admin/                   (月報檢視 + CRUD 員工)
│  │  │  │  └─ AdminTabs.tsx
│  │  │  └─ api/
│  │  │     ├─ employees/route.ts    (GET 員工列表)
│  │  │     ├─ punch/route.ts        (POST 打卡 → 寫 raw_punches → 觸發重算)
│  │  │     ├─ amend/route.ts        (POST 補登 → 寫 amendments)
│  │  │     └─ admin/                (受 ADMIN_SECRET 保護)
│  │  ├─ components/
│  │  │  ├─ EmployeeGrid.tsx
│  │  │  ├─ PinPad.tsx
│  │  │  └─ AmendForm.tsx
│  │  ├─ lib/
│  │  │  ├─ analyzer/                ◄── 從 pokebeeClock-analyzer port 搬入
│  │  │  ├─ sheets.ts                (Google Sheets wrapper)
│  │  │  ├─ analyzer_bridge.ts       (raw_punches → analyzer → analyzed/summary)
│  │  │  └─ constants.ts
│  │  └─ types/
│  ├─ public/manifest.json
│  ├─ package.json
│  └─ (其他 Next.js 設定檔抄 pokebeeExpense)
├─ docs/
│  ├─ plan.md                        (複製本檔)
│  └─ hours_analyzer_spec.md         (從 pokebee 複製 ground truth)
├─ CLAUDE.md                         (playbook，仿 pokebeeExpense/app/CLAUDE.md)
└─ README.md
```

## 重算策略

每次 `/api/punch` 或 `/api/amend` 寫入後：
1. 從 `raw_punches` 讀該員工**該月**全部 events
2. 呼叫 `analyzeEmployee(name, events)`（ported）→ 得到 records + summary
3. 刪 `analyzed_YYYY-MM` 中該員工所有 row，寫回新結果
4. 更新 `summary_YYYY-MM` 該員工那組

低頻場景（一天幾十次打卡），Google Sheets API quota 完全撐得住。

**注意**：補登目前不自動觸發重算（status=pending）。月底審核後由管理者手動在 sheet 調整或另跑工具。MVP 不做自動合併。

## 安全

- iPad 維持管理者 Google session 常駐（主要屏障）
- `/admin` 與 admin API 路由：`Authorization: Bearer $ADMIN_SECRET`（env var）
- PIN 以 sha256 儲存，不存明文
- Service account JSON 走 Vercel env var（`GOOGLE_SA_JSON`），不進 repo
- Vercel 原生 HTTPS，解決現行 pokebee ngrok 問題

## 實作階段

**MVP（階段 1）**
- [ ] 複製 pokebeeExpense 骨架 → 可跑 `npm run dev`
- [ ] `employees` sheet + `/api/employees` + 打卡主頁 UI（員工格 + PinPad）
- [ ] `raw_punches` sheet + `/api/punch`（只寫入，還不重算）
- [ ] 整合 ported analyzer → 寫入 `analyzed_*` / `summary_*`
- [ ] `/amend` 頁 + `/api/amend`

**階段 2**
- [ ] `/admin` 月報檢視頁（讀 `summary_*` 顯示）
- [ ] `/admin` 員工管理 CRUD
- [ ] PWA manifest + install-to-home 驗證

**階段 3（可選）**
- [ ] 月底管理者 UI 把 amendments 合併進 raw_punches（目前手動）
- [ ] iCHEF CSV 匯入路徑（如果還需要）
- [ ] LINE 通知

## 跨專案關係

```
pokebee/                           pokebeeClock/              pokebeeClock-analyzer/
├─ clock_in_out_analyzer.py  ──►   src/lib/analyzer/    ◄──   src/  (port 產出)
│  (ground truth, 保留)            (搬入使用)                  tests/ (parity tests)
└─ docs/clock_in_out/
   hours_analyzer_spec.md    ──►   docs/hours_analyzer_spec.md (copy)
```

- **pokebee**：保留 Python analyzer 與 iCHEF CSV CLI 流程作為備援與 ground truth
- **pokebeeClock-analyzer**：獨立 port package，一次性任務，產出後使命結束
- **pokebeeClock**：生產環境，serving code

## 驗證

1. **analyzer parity**：已由 port 專案保證（見 `plan_analyzer_port.md`）
2. **整合**：建測試用 Google Sheet，跑 `/api/punch` 幾輪，檢查三張 sheet 狀態
3. **手動**：iPad Safari 開 Vercel URL → install to home → 模擬一天打卡流程 → 月底 `summary_*` 對照 Python 版輸出
4. **補登**：送補登 → 檢查 `amendments` 有紀錄、`analyzed_*` 不受影響

## 仍待確認

- Service account credential 是沿用 pokebeeExpense 那組還是新建？（建議新建，權限隔離）
- 員工 PIN 忘記時的 reset 流程？（MVP：管理者直接改 sheet）
- 跨月第一次打卡時 `analyzed_YYYY-MM` tab 要預先建還是自動建？（建議自動建）
- 時區：Vercel 預設 UTC，server_ts 要明確轉 Asia/Taipei
