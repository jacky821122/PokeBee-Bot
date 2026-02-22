# Development Environment Setup

This guide helps you set up the PokeBee-Bot development environment on both NAS and WSL2/local PC.

## Prerequisites

- Python 3.10
- Conda (NAS) or venv (WSL2)
- `.env` file with LINE API credentials

## Setup on NAS (Current)

```sh
# Create/update conda environment
conda env create -f environment.yml

# Or update existing environment
conda env update -f environment.yml --prune

# Activate and load env vars
conda activate ichef-report
cd ~/jacky821122/pokebee/
source .env
```

## Setup on WSL2/Local PC

### Option 1: Using venv (Recommended for WSL2)

```sh
# Navigate to project
cd /path/to/pokebee

# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Load environment variables
source .env

# Verify installation
python -c "import flask; import linebot; import pandas; print('✓ All dependencies installed')"
```

### Option 2: Using conda (If you prefer)

```sh
cd /path/to/pokebee

# Create conda environment from file
conda env create -f environment.yml

# Activate environment
conda activate ichef-report

# Load environment variables
source .env
```

## Syncing Dependencies

### After installing new packages on either environment:

**On NAS (conda):**
```sh
# After pip install <package> in conda env
pip freeze > requirements.txt

# Manually update environment.yml with new packages
```

**On WSL2 (venv):**
```sh
# After pip install <package>
pip freeze > requirements.txt

# Commit and push
git add requirements.txt environment.yml
git commit -m "deps: add <package>"
git push
```

**On the other machine:**
```sh
# Pull changes
git pull

# Update environment
pip install -r requirements.txt  # if using venv
# OR
conda env update -f environment.yml --prune  # if using conda
```

## Quick Verification

Test that everything works:

```sh
# Check Python version
python --version  # should be 3.10.x

# Test imports
python -c "
import flask
import linebot
import pandas
import sqlite3
print('✓ Environment ready')
"

# Test app loads
python -c "from line_bot_app import app; print('✓ App imports successfully')"
```

## Common Issues

### Different Python versions
Both environments should use Python 3.10. Check with `python --version`.

### Missing .env file
Copy `.env.example` to `.env` and fill in your LINE credentials.

### SQLite database not found
Initialize the database:
```sh
sqlite3 data/db/ichef.db < create_tables.sql
```

### Port already in use
The Flask app uses port 8000. Kill existing process or change the port in `line_bot_app.py`.
