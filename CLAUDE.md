# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PokeBee-Bot is a LINE chatbot for a poke bowl restaurant that imports iCHEF POS CSV exports into SQLite and generates daily/weekly sales analytics reports in Traditional Chinese.

## Workflow

After completing any code or documentation changes, always commit and push immediately without waiting to be asked.

## Commands

```sh
# Start the Flask webhook server (port 8000)
python line_bot_app.py

# Expose local server to the internet for LINE webhook
ngrok_start

# Initialize or reset the SQLite database
sqlite3 data/db/ichef.db < create_tables.sql

# Manually import iCHEF order CSV
python import_csv.py

# Manually import iCHEF modifier/add-on CSV
python import_modifier_csv.py

# Run daily metrics for a date
python daily_metrics.py

# Generate weekly report (CLI)
python weekly_generator.py --start YYYY-MM-DD --end YYYY-MM-DD

# Generate weekly report via LINE bot
# Send: 週報 YYYY-MM-DD YYYY-MM-DD
# Or:   週報 上週
```

```sh
# Run tests
python -m pytest tests/ -v
```

Tests cover `metrics_common` (pure unit, 32 cases) and `calculate_daily_metrics` (integration with in-memory SQLite, 4 cases). CI runs on every push via GitHub Actions.

## Architecture

**Data flow:**
1. User uploads a CSV to the LINE bot (1:1 only) → `handle_file_message()` saves to `data/ichef/raw/YYYY-MM/` and calls `import_csv()` or `import_modifier_csv()` → inserted into SQLite
2. User sends `分析 YYYY-MM-DD` (or `分析 今天` / `分析 昨天`) → `calculate_daily_metrics()` → `render_daily_report()` → reply via LINE API
3. User sends `週報 YYYY-MM-DD YYYY-MM-DD` (or `週報 上週`) → `calculate_weekly_metrics()` → `render_weekly_report()` → reply via LINE API

**Module responsibilities:**
- `line_bot_app.py` — Flask webhook; routes LINE events to handlers; only allows hardcoded `ALLOWED_USER_IDS`
- `metrics_common.py` — central config (see below) and shared data access: `load_orders()`, `load_modifier()`, `preprocess_orders()`, bowl/protein counting helpers
- `daily_metrics.py` — computes daily KPIs (bowls, revenue, lunch/dinner split, peak hours, dine-in/takeout, proteins, payment methods)
- `weekly_generator.py` — aggregates metrics across a date range for the weekly report
- `report_renderer.py` — formats metrics dicts into LINE message text
- `import_csv.py` / `import_modifier_csv.py` — parse iCHEF CSVs and upsert into SQLite

**Database:** SQLite at `data/db/ichef.db`
- `raw_orders`: order records (checkout_time, items_text, invoice_amount, payment_method, order_status, …). Deduped by UNIQUE(invoice_number, checkout_time).
- `modifier_summary`: add-on/modifier items with date ranges.

**Key configuration in `metrics_common.py`** — modify these to adjust business rules:
```python
BUSINESS_HOURS = {
    "lunch":  {"start": "11:00", "end": "14:30"},
    "dinner": {"start": "16:30", "end": "20:00"},
}
BOWLS_KEYWORDS = ["碗"]          # item must contain this to be a bowl
EXCLUDE_ITEMS  = ["提袋", "加購"]  # excluded from bowl count
PROTEIN_RULES  = {               # protein → list of required keywords in item name
    "chicken": ["雞胸肉"],
    "tofu":    ["豆腐"],
    "shrimp":  ["鮮蝦"],
    "salmon":  ["鮭魚"],
    "tuna":    ["鮪魚"],
    "pork":    ["壽喜燒豬"],
}
SET_MEAL_RULES = { ... }         # maps set-meal names to their protein composition
```

**Filters applied before any analysis:**
- `order_status NOT LIKE '%Voided%'` (SQL level)
- `invoice_amount > 0` (excludes employee/zero-cost orders)

## Design Decisions & Constraints

### iCHEF data limitations
iCHEF has no webhook or event-based API. All data must be manually downloaded as CSV exports and uploaded.

There are two fundamentally different CSV types:

| | Order CSV (`Payment_Void Record_*.csv`) | Modifier CSV (`modifier*.csv`) |
|---|---|---|
| Granularity | Per-order, with timestamp | Aggregate totals only, no per-order timestamp |
| Date range | Exact checkout_time per row | Only a date range total |
| How to get | Upload via LINE bot | Manual download, weekly cadence |
| Used in | Daily + weekly reports | Weekly report only |

Because modifier data has no timestamp granularity, it cannot be attributed to individual days.

### Report audience and purpose

**Daily report** (`分析 YYYY-MM-DD` via LINE bot):
- Audience: shareholders — quick daily pulse check
- Philosophy: show only what shareholders actually care about; keep it concise
- Intentionally excludes: protein breakdown, cloud kitchen ratio
  - Protein: modifier add-ons contribute significantly to protein counts; without them the bowl-only number is misleading
  - Cloud kitchen: implicit/background data, not a shareholder-facing metric

**Weekly report** (`週報 上週` via LINE bot, or `weekly_generator.py --start ... --end ...` via CLI):
- Audience: primarily LLM for advanced analysis; secondarily shareholders via manual paste
- Available both via LINE bot (`週報 YYYY-MM-DD YYYY-MM-DD` / `週報 上週`) and via CLI
- Includes protein from all sources (bowls + add-ons + set meals + non-bowl items)
- Modifier data is loaded and merged here, giving a complete protein picture

### Data update cadence
- Order data: any time, via LINE bot file upload
- Modifier data: once per week, manual CLI import (`python import_modifier_csv.py`)

### Weekly report workflow in practice
Owner manually downloads modifier CSV from iCHEF backend → runs `import_modifier_csv.py` → sends `週報 上週` via LINE bot → pastes the output text into an LLM for deeper analysis. The weekly report output is intentionally structured for LLM consumption (structured text, complete protein breakdown) rather than human skimming.

There is no automated scheduling — owner triggers the report manually after updating modifier data, which is the natural trigger point anyway.

## Store Context

### Menu — confirmed item names from production iCHEF CSV (2026-02)

**Individual bowls:**
| Item | Price |
|---|---|
| 雞胸肉自選碗 | $149 |
| 嚴選生鮭魚自選碗 | $171 |
| 鮮蝦自選碗 | $153 |
| 生鮪魚自選碗 | $198 |
| 壽喜燒豬自選碗 | $160 |
| 豆腐自選碗 | (unknown, inferred from PROTEIN_RULES) |

**Set meals (套餐):**
| Item | Price | Protein composition |
|---|---|---|
| 高蛋白健身碗 | $189 | 2× chicken |
| 海味雙魚碗 | $234 | 1× salmon + 1× tuna |
| 清爽佛陀碗 | — | 1× tofu |
| 經典均衡碗 | — | 1× chicken |

**Add-ons (modifier / non-bowl items):**
- `豆腐 80g $0.0` — counts as tofu protein (non-bowl)
- `嚴選生鮭魚 45g $0.0` — counts as salmon protein (non-bowl)
- `加購一份壽喜燒豬 $50` — counts as pork protein (non-bowl)
- `提袋 $2.0` — excluded from all counts (EXCLUDE_ITEMS)

**Business hours:**
- Lunch: 11:00–14:30
- Dinner: 16:30–20:00

**Order types:** `Dine In` / `Takeout` / `Delivery` (Delivery maps to cloud kitchen = Online Store order_source)

**Payment methods:** Cash (`現金`), LinePay — anything else falls through to "Other"
