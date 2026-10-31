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
python main.py --full

# Incremental load (daily production use)
python main.py

# Single entity
python main.py --entity deals
python main.py --entity contacts --full
```

### Development Setup

```bash
# Recrear venv y instalar dependencias (usar python3, no python)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Environment setup - copiar .env.example a .env y configurar:
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
   - `SQLServerLoader` base class con conexión via **pymssql** (no pyodbc)
   - Extended loaders in `sql_loader_extended.py` for additional entities
   - **Auto-creación de tablas:** `ensure_schema_exists()` se llama al conectar — crea todas las tablas si no existen, sin necesidad de scripts SQL manuales
   - **BULK INSERT pattern** (critical for performance):
     1. Create temp table (`#temp_entity`)
     2. `loader._bulk_insert()` — inserta todas las filas en un único `INSERT ... VALUES (r1),(r2),...` (un solo round-trip)
     3. Single MERGE from temp → final table
     4. Count INSERTs/UPDATEs via `OUTPUT $action`
     5. Cleanup and commit
   - **deal_products uses DELETE + INSERT** (not MERGE) to avoid duplicate key conflicts
   - **Placeholders:** usar `%s` (pymssql), NO `?` (pyodbc)

3. **Orchestration Layer** (`main.py`)
   - Maps entity names to extractor methods
   - Maps entity names to loader functions
   - Handles incremental logic via `etl_control` table
   - Logs execution stats to database
   - After all entities, executes the Stored Procedures defined in `STORED_PROCEDURES`

4. **SP Runner Layer** (`etl/sp_runner.py`)
   - `run_stored_procedures(loader, sp_list)` — ejecuta una lista de SPs secuencialmente
   - `execute_sp(loader, sp_name)` — ejecuta un SP individual y registra auditoría en `etl_control`
   - El nombre del SP se usa como `entity_name` en `etl_control` para trazabilidad
   - Lista de SPs configurada en `STORED_PROCEDURES` al inicio de `main.py`

### Configuration (`config.py`)

- Credenciales y conexión vienen **exclusivamente del `.env`** — ningún valor hardcodeado en `config.py`
- `SQL_SERVER_CONNECTION_PARAMS`: dict con parámetros para pymssql (`server`, `port`, `database`, `user`, `password`)
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
3. Create `upsert_ENTITY()` function in `sql_loader_extended.py` using BULK INSERT pattern (placeholders `%s`)
4. Add `CREATE TABLE` DDL en `ensure_schema_exists()` en `sql_loader.py` (NO en script SQL externo)
5. Map entity in `main.py`:
   - Add extraction branch (line ~123-156)
   - Add loading branch (line ~171-201)

## Common Patterns

**Temp table + MERGE pattern:**
```python
# Create temp table
cursor.execute("CREATE TABLE #temp_entity (...)")

# Bulk insert a temp (un solo INSERT multi-row, un solo round-trip)
loader._bulk_insert(cursor, "#temp_entity", ["col1","col2",...], insert_data)

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

- All tables in `freshsale` schema (SQL Server 2022 on Linux/Ubuntu)
- Standard ETL columns: `etl_created_at DATETIME NULL DEFAULT GETDATE()`, `etl_updated_at DATETIME NULL DEFAULT GETDATE()`
- `etl_control` table tracks last successful run per entity
- Most tables use Freshsales `id BIGINT NOT NULL PRIMARY KEY`
- Exception: `deal_products` has `id BIGINT IDENTITY(1,1)` + `freshsale_id BIGINT NULL`
- `fact_deals_products` es una tabla de reporting calculada por el SP `dbo.act_fact_deals_products` — **no es gestionada por el ETL**

### Tablas gestionadas por el ETL

| Tabla | PK | Notas |
|---|---|---|
| `etl_control` | `id INT IDENTITY` | Control de ejecución |
| `etl_log` | `id INT IDENTITY` | Logs |
| `users` | `id BIGINT` | |
| `teams` | `id BIGINT` | |
| `team_users` | `id INT IDENTITY` | Sin FK |
| `pipelines` | `id BIGINT` | |
| `stages` | `id BIGINT` | |
| `deals` | `id BIGINT` | `name NVARCHAR(MAX)` |
| `deal_products` | `id BIGINT IDENTITY` | Sin FK a deals |
| `contacts` | `id BIGINT` | |
| `sales_accounts` | `id BIGINT` | |
| `leads` | `id BIGINT` | Deshabilitado (403) |
| `tasks` | `id BIGINT` | |
| `appointments` | `id BIGINT` | |
| `sales_activities` | `id BIGINT` | Columnas: `notes`, `activity_type` |
| `products` | `id BIGINT` | |
| `forecast_categories` | `id BIGINT` | |
| `deal_predictions` | `id BIGINT` | |
| `deal_history` | `id BIGINT IDENTITY` | Historial de cambios de deals. **Nunca se borra** |
| `deal_contacts` | `(deal_id, contact_id)` | Todos los contactos de cada deal (`deals.contact_id` es solo el primero) |
| `deal_notes` | `(id, deal_id)` | Notas de los deals. Los informes leen `deal_id`, `created_at`, `description` |
| `lead_sources` | `id BIGINT` | Catálogo de orígenes (`deals.lead_source_id`) |

### Origen, creador y notas

- `extract_deals()` usa `include=...,source,creater`: sin eso `lead_source_id` y `creater_id` vienen vacíos. `creater_id` se guarda en `deals.creator_id`.
- `deal_contacts` se carga en `upsert_deals()` (DELETE + INSERT de los deals que trajeron `contact_ids`).
- `deal_notes`: `main.load_deal_notes()` corre después de deals y pide `/deals/{id}?include=notes` solo para los deals nuevos o con `updated_at` distinto (`loader.deals_changed_ids`); agregar una nota cambia el `updated_at` del deal. Si nunca se cargaron o la última carga falló (`etl_control`, entity `deal_notes`), barre todos los deals. DELETE + INSERT por deal procesado.
- `vw_deals_estado`: `es_ganado` / `es_perdido` (de `stages.type`), `fecha_ganado` (primera entrada a Closed Won según el historial), dueño, creador y origen con nombre. "Lead convertido" = deal ganado.

### Historial de deals (`deal_history`)

- `upsert_deals()` llama a `_record_deal_history()` **antes del MERGE** y en la misma transacción: compara `#temp_deals` con `freshsale.deals` y guarda una fila por campo que cambió.
- Campos vigilados en `SQLServerLoader._HISTORY_FIELDS`: etapa, pipeline, monto, `expected_close`, `closed_date`, dueño, probabilidad, Commit (`forecast_category`), `cf_valor_total_de_contrato`, `cf_tipo_de_servicio`, `is_deleted`. Para vigilar otro campo, agregarlo a esa lista.
- Los valores se normalizan a texto antes de comparar (montos `DECIMAL(18,2)`, fechas `AAAA-MM-DD`) para no registrar cambios falsos.
- `tipo`: `inicial` (estado al activar el historial, 30-oct-2026), `nuevo` (deal que no existía), `cambio`. Al contar cambios, excluir `inicial`.
- `fecha_cambio_fs`: hora del cambio según Freshsales (`stage_updated_time` para la etapa, `updated_at` para el resto). `detectado_en`: hora en que lo vio el ETL.
- Vistas: `vw_deal_history` (con nombres en vez de IDs) y `vw_deal_stage_history` (etapa origen/destino, días en la etapa, `es_ganado`).
- **Ojo con `_bulk_insert`:** usa un `INSERT ... VALUES` multi-fila; si en una columna se mezclan textos y números, SQL Server convierte todo al tipo numérico del literal y puede redondear. La API entrega los montos como texto: no convertirlos a `float` en Python.

## Important Notes

- **`--skip-schema` es irrelevante** — las tablas se crean automáticamente al conectar via `ensure_schema_exists()`
- **Driver: pymssql** (no pyodbc) — requerido para soporte de `NVARCHAR(MAX)` en bulk inserts
- **deal_products requires deals** - products are extracted as part of deals process
- **stages requires pipelines** - stages come from pipelines API response
- **Leads entity disabled** - API key lacks permissions (403 error)
- **Cron/scheduled execution:** Use incremental mode without `--full` flag
- **Horario en producción:** el cron llama a `run_etl.sh` cada hora y el script decide si corre según la hora de **Colombia** (16, 20, 0, 4, 8, 12 h). `contact_lists` (~36 min) solo corre a las 20 h; el resto con `--exclude contact_lists`. Con argumentos, `run_etl.sh` corre de inmediato (uso manual). El servidor está en hora de Chile, que cambia con el horario de verano: por eso el horario se decide en el script y no en el crontab.
- **`--exclude`:** `python main.py --exclude contact_lists,contacts` omite entidades en esa corrida.
- **First-time setup:** Use `--full` to populate all tables initially
- **`fact_deals_products`** se actualiza automáticamente al final del ETL via `etl/sp_runner.py` ejecutando `dbo.act_fact_deals_products`
- **Agregar un nuevo SP:** añadirlo a `STORED_PROCEDURES` en `main.py` — se ejecutará automáticamente y quedará auditado en `etl_control`
