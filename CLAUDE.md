# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PokeBee-Bot is a LINE chatbot for a poke bowl restaurant that imports iCHEF POS CSV exports into SQLite and generates daily/weekly sales analytics reports in Traditional Chinese.

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

# Generate weekly report
python weekly_generator.py
```

There is no test suite. Testing is done manually via the LINE bot.

## Architecture

**Data flow:**
1. User uploads a CSV to the LINE bot (1:1 only) → `handle_file_message()` saves to `data/ichef/raw/YYYY-MM/` and calls `import_csv()` or `import_modifier_csv()` → inserted into SQLite
2. User sends `分析 YYYY-MM-DD` (or `分析 今天` / `分析 昨天`) → `calculate_daily_metrics()` → `render_daily_report()` → reply via LINE API

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
}
SET_MEAL_RULES = { ... }         # maps set-meal names to their protein composition
```

**Filters applied before any analysis:**
- `order_status NOT LIKE '%Voided%'` (SQL level)
- `invoice_amount > 0` (excludes employee/zero-cost orders)
