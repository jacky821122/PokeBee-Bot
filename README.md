# PokeBee-Bot

[![CI](https://github.com/jacky821122/PokeBee-Bot/actions/workflows/ci.yml/badge.svg)](https://github.com/jacky821122/PokeBee-Bot/actions/workflows/ci.yml)

LINE chatbot for a poke bowl restaurant. Imports iCHEF POS CSV exports into SQLite and generates daily/weekly sales analytics reports in Traditional Chinese.

## Running

```sh
# Start Flask webhook server (port 8000)
python line_bot_app.py

# Expose to internet for LINE webhook
ngrok_start
```

## LINE Bot Commands

| Command | Description |
|---|---|
| `分析 YYYY-MM-DD` | Daily report for a specific date |
| `分析 今天` / `分析 昨天` | Daily report for today / yesterday |
| `週報 YYYY-MM-DD YYYY-MM-DD` | Weekly report for date range |
| `週報 上週` | Weekly report for last week |
| Upload CSV file | Import iCHEF order or modifier CSV |

## Data Import

iCHEF has no API — all data comes from manually downloaded CSV exports.

```sh
# Import order CSV (also done automatically via LINE bot file upload)
python import_csv.py

# Import modifier/add-on CSV (weekly, CLI only)
python import_modifier_csv.py

# Reset database
sqlite3 data/db/ichef.db < create_tables.sql
```

## CLI Report Generation

```sh
# Daily metrics
python daily_metrics.py --date YYYY-MM-DD

# Weekly report
python weekly_generator.py --start YYYY-MM-DD --end YYYY-MM-DD
```

## Employee Hours

Calculate employee clock-in/out hours from iCHEF CSV exports:

```sh
python clock_in_out_analyzer.py "data/clock_in_out/Clock-in_out Record_YYYY-MM-DD~YYYY-MM-DD.csv"
```

Outputs a console summary (normal hours, overtime, flagged shifts) and a detailed report at `data/clock_in_out/clock_report_YYYY-MM.{csv,xlsx}`.

## Testing

```sh
python -m pytest tests/ -v
```

36 tests covering `metrics_common` (pure unit) and `calculate_daily_metrics` (in-memory SQLite integration). CI runs on every push to `main`.

## Development

**Environment:**
```sh
conda env create -f environment.yml
conda activate ichef-report
```

**Key config** — all business rules live in `metrics_common.py`:
- `BUSINESS_HOURS` — lunch/dinner time windows
- `BOWLS_KEYWORDS` / `EXCLUDE_ITEMS` — bowl counting rules
- `PROTEIN_RULES` / `SET_MEAL_RULES` — protein attribution（包含新蛋白質 `pork`，並支援新主餐 `壽喜燒豬自選碗`）
