# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ETL system that extracts data from Freshsales CRM API and loads it into SQL Server using optimized BULK INSERT patterns. The system supports both full and incremental loads for 13+ entities (deals, contacts, sales accounts, products, etc.).

## Key Commands

### Running the ETL

```bash
# Activate virtual environment first
source venv/bin/activate

# Full load (first time or force refresh)
python main.py --full --skip-schema

# Incremental load (daily production use)
python main.py --skip-schema

# Single entity
python main.py --entity deals --skip-schema
python main.py --entity contacts --full --skip-schema

# With schema creation (only if tables don't exist)
python main.py --full
```

### Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Environment setup - configure .env with:
# - FRESHSALE_DOMAIN, FRESHSALE_API_KEY
# - REP_DB_HOST, REP_DB_PORT, REP_DB_NAME, REP_DB_USER, REP_DB_PASSWORD
```

## Architecture

### Three-Layer Pattern

1. **Extraction Layer** (`etl/freshsale_extractor.py`)
   - `FreshsaleExtractor` class handles all API calls
   - Pagination: 100 records/page with automatic continuation
   - Rate limiting: 0.5s delay between requests
   - Retry logic: 3 attempts with exponential backoff
   - Filter support: Uses view filter IDs to get "All Deals", "All Contacts", etc.
   - Special handling: `extract_deals()` uses `?include=products` to fetch deal_products in same call

2. **Loading Layer** (`etl/sql_loader.py` + `etl/sql_loader_extended.py`)
   - `SQLServerLoader` base class with core upsert functions
   - Extended loaders in `sql_loader_extended.py` for additional entities
   - **BULK INSERT pattern** (critical for performance):
     1. Create temp table (`#temp_entity`)
     2. Insert all records individually to temp table (avoids buffer overflow)
     3. Single MERGE from temp → final table
     4. Count INSERTs/UPDATEs via `OUTPUT $action`
     5. Cleanup and commit
   - **deal_products uses DELETE + INSERT** (not MERGE) to avoid duplicate key conflicts

3. **Orchestration Layer** (`main.py`)
   - Maps entity names to extractor methods
   - Maps entity names to loader functions
   - Handles incremental logic via `etl_control` table
   - Logs execution stats to database

### Configuration (`config.py`)

- `ENTITIES_CONFIG`: Central registry of all entities with:
  - `enabled`: Whether to process
  - `filter_id`: Freshsales view filter (28001560042 = "All Deals")
  - `incremental`: True = only fetch records modified since last run
  - `date_field`: Field to use for incremental queries (usually `updated_at`)

### Critical Implementation Details

**deal_products extraction:**
- Products are extracted alongside deals using `?include=products` parameter
- After upserting deals, `_extract_and_load_deal_products()` is called
- Uses DELETE + INSERT pattern (not MERGE) because:
  - Same product can appear multiple times in same deal
  - No unique key exists (freshsale_id + deal_id + product_id still has duplicates)
  - DELETE all products for processed deals, then INSERT fresh data

**Incremental loads:**
- `get_last_extraction_date()` reads `etl_control` table
- Passes `last_updated` timestamp to Freshsales API: `?updated_since={timestamp}`
- Only entities with `incremental: True` support this

**stages extraction:**
- Stages come from pipelines API response (`deal_stages` array)
- `extract_pipelines()` gets pipelines, then stages are extracted from nested data
- Both pipelines and stages can be loaded separately

**forecast_categories and deal_predictions:**
- Extracted from `/api/settings/deals/fields` endpoint
- Field metadata contains `choices` array with category/prediction options
- Small reference tables, always full load

## Adding a New Entity

1. Add to `ENTITIES_CONFIG` in `config.py`
2. Create `extract_ENTITY()` method in `freshsale_extractor.py`
3. Create `upsert_ENTITY()` function in `sql_loader_extended.py` using BULK INSERT pattern
4. Add table schema to `sql/01_create_schema.sql`
5. Map entity in `main.py`:
   - Add extraction branch (line ~123-156)
   - Add loading branch (line ~171-201)

## Common Patterns

**Temp table + MERGE pattern:**
```python
# Create temp table
cursor.execute("CREATE TABLE #temp_entity (...)")

# Insert to temp (individual inserts to avoid buffer issues)
for record in data:
    cursor.execute("INSERT INTO #temp_entity (...) VALUES (...)", values)

# MERGE temp → final
cursor.execute("""
    MERGE entity AS target
    USING #temp_entity AS source ON target.id = source.id
    WHEN MATCHED THEN UPDATE SET ...
    WHEN NOT MATCHED THEN INSERT (...) VALUES (...)
    OUTPUT $action
""")

# Count results
for result in cursor.fetchall():
    if result[0] == 'INSERT': stats["inserted"] += 1
    elif result[0] == 'UPDATE': stats["updated"] += 1
```

**DELETE + INSERT pattern (for entities with duplicate issues):**
```python
# Delete existing records for this batch
cursor.execute("DELETE FROM entity WHERE id IN (SELECT DISTINCT id FROM #temp_entity)")

# Insert all fresh records
cursor.execute("INSERT INTO entity (...) SELECT ... FROM #temp_entity")
stats["inserted"] = cursor.rowcount
```

## Database Schema

- All tables in `freshsale` schema
- Standard ETL columns: `etl_created_at`, `etl_updated_at`
- `etl_control` table tracks last successful run per entity
- Most tables use Freshsales `id` as primary key
- Exception: `deal_products` has auto-increment `id` + `freshsale_id` column for original ID

## Important Notes

- **Always use `--skip-schema`** in production (schema already exists)
- **deal_products requires deals** - products are extracted as part of deals process
- **stages requires pipelines** - stages come from pipelines API response
- **Leads entity disabled** - API key lacks permissions (403 error)
- **Cron/scheduled execution:** Use incremental mode without `--full` flag
- **First-time setup:** Use `--full` to populate all tables initially
