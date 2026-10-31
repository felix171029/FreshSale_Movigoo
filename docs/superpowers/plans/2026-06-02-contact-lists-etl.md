# Contact Lists ETL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraer la relación contacto ↔ lista de marketing desde Freshsales y cargarla en una nueva tabla `freshsale.contact_lists` en SQL Server.

**Architecture:** Se itera `GET /api/lists` (paginado) para obtener todas las listas, luego por cada lista se llama `GET /api/contacts/lists/{id}` (paginado) para obtener sus contactos. El resultado es una tabla puente que se reemplaza completamente en cada corrida (TRUNCATE + INSERT), ya que no existe campo `updated_at` en la membresía de listas.

**Tech Stack:** Python 3, pymssql, Freshsales REST API, SQL Server 2022

---

## Archivos a modificar / crear

| Archivo | Cambio |
|---|---|
| `etl/freshsale_extractor.py` | Agregar método `extract_contact_lists()` |
| `etl/sql_loader.py` | Agregar DDL de `freshsale.contact_lists` en `ensure_schema_exists()` |
| `etl/sql_loader_extended.py` | Agregar función `upsert_contact_lists()` |
| `config.py` | Agregar entrada `contact_lists` en `ENTITIES_CONFIG` |
| `main.py` | Agregar rama de extracción y carga para `contact_lists` |

---

## Task 1: DDL — Crear tabla `freshsale.contact_lists`

**Files:**
- Modify: `etl/sql_loader.py` — agregar DDL en `ensure_schema_exists()`

- [ ] **Step 1: Agregar el CREATE TABLE después del bloque de `deal_products`**

Buscar en `etl/sql_loader.py` el bloque de `deal_products` dentro de `ensure_schema_exists()` e insertar el siguiente DDL a continuación (como nuevo elemento de la lista de sentencias SQL):

```python
# contact_lists
"""IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.contact_lists') AND type = 'U')
CREATE TABLE freshsale.contact_lists (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    contact_id BIGINT NOT NULL,
    list_id BIGINT NOT NULL,
    list_name NVARCHAR(500) NULL,
    etl_created_at DATETIME NULL DEFAULT GETDATE()
)""",
```

- [ ] **Step 2: Verificar que no hay errores de sintaxis**

```bash
cd /Users/felix/FreshSale_Movigoo && source venv/bin/activate && python -c "from etl.sql_loader import SQLServerLoader; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add etl/sql_loader.py
git commit -m "feat: add DDL for freshsale.contact_lists bridge table"
```

---

## Task 2: Extractor — `extract_contact_lists()`

**Files:**
- Modify: `etl/freshsale_extractor.py` — agregar método al final de la clase `FreshsaleExtractor`

- [ ] **Step 1: Agregar el método al final de `FreshsaleExtractor`**

Insertar antes del último método de la clase (o al final del archivo antes de cualquier función suelta):

```python
def extract_contact_lists(self) -> List[Dict]:
    """Extrae la relación contacto-lista iterando todas las listas y sus contactos."""
    logger.info("Extracting contact lists...")
    records = []

    # 1. Obtener todas las listas (paginado)
    all_lists = []
    page = 1
    while True:
        data = self._make_request(f"{self.base_url}/lists", {"page": page})
        if not data:
            break
        lists_page = data.get("lists", [])
        all_lists.extend(lists_page)
        meta = data.get("meta", {})
        if page >= meta.get("total_pages", 1) or not lists_page:
            break
        page += 1

    logger.info(f"Found {len(all_lists)} lists")

    # 2. Por cada lista, obtener sus contactos (paginado)
    for lst in all_lists:
        list_id = lst["id"]
        list_name = lst.get("name")
        contact_page = 1
        while True:
            contact_data = self._make_request(
                f"{self.base_url}/contacts/lists/{list_id}",
                {"page": contact_page}
            )
            if not contact_data:
                break
            contacts = contact_data.get("contacts", [])
            for c in contacts:
                records.append({
                    "contact_id": c["id"],
                    "list_id": list_id,
                    "list_name": list_name,
                })
            meta = contact_data.get("meta", {})
            if contact_page >= meta.get("total_pages", 1) or not contacts:
                break
            contact_page += 1

    logger.info(f"Total contact-list records extracted: {len(records)}")
    return records
```

- [ ] **Step 2: Verificar importación**

```bash
cd /Users/felix/FreshSale_Movigoo && source venv/bin/activate && python -c "from etl.freshsale_extractor import FreshsaleExtractor; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Prueba rápida contra la API real**

```bash
cd /Users/felix/FreshSale_Movigoo && source venv/bin/activate && python -c "
from etl.freshsale_extractor import FreshsaleExtractor
import os; from dotenv import load_dotenv; load_dotenv()
e = FreshsaleExtractor(os.getenv('FRESHSALE_DOMAIN'), os.getenv('FRESHSALE_API_KEY'))
records = e.extract_contact_lists()
print(f'Total records: {len(records)}')
if records:
    print('Sample:', records[0])
"
```
Expected: número de registros > 0 y un dict con `contact_id`, `list_id`, `list_name`.

- [ ] **Step 4: Commit**

```bash
git add etl/freshsale_extractor.py
git commit -m "feat: add extract_contact_lists() to FreshsaleExtractor"
```

---

## Task 3: Loader — `upsert_contact_lists()`

**Files:**
- Modify: `etl/sql_loader_extended.py` — agregar función al final del archivo

- [ ] **Step 1: Agregar la función al final de `sql_loader_extended.py`**

```python
def upsert_contact_lists(loader, records: List[Dict]) -> Dict[str, int]:
    """Reemplaza completamente la tabla contact_lists con los datos actuales (TRUNCATE + INSERT)."""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not records:
        logger.info("No contact_lists records to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        logger.info(f"Creating temp table for {len(records)} contact_lists records...")
        cursor.execute("""
            CREATE TABLE #temp_contact_lists (
                contact_id BIGINT,
                list_id BIGINT,
                list_name NVARCHAR(500)
            )
        """)

        insert_data = [
            (r["contact_id"], r["list_id"], r["list_name"])
            for r in records
        ]

        loader._bulk_insert(
            cursor,
            "#temp_contact_lists",
            ["contact_id", "list_id", "list_name"],
            insert_data
        )

        # Reemplazo completo: truncar y reinsertar desde temp
        cursor.execute("TRUNCATE TABLE freshsale.contact_lists")
        cursor.execute("""
            INSERT INTO freshsale.contact_lists (contact_id, list_id, list_name)
            SELECT contact_id, list_id, list_name FROM #temp_contact_lists
        """)
        stats["inserted"] = cursor.rowcount

        cursor.execute("DROP TABLE #temp_contact_lists")
        loader.connection.commit()
        logger.info(f"contact_lists loaded: {stats['inserted']} inserted")

    except Exception as e:
        logger.error(f"Failed to load contact_lists: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(records)
    finally:
        cursor.close()

    return stats
```

- [ ] **Step 2: Verificar importación**

```bash
cd /Users/felix/FreshSale_Movigoo && source venv/bin/activate && python -c "from etl.sql_loader_extended import upsert_contact_lists; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add etl/sql_loader_extended.py
git commit -m "feat: add upsert_contact_lists() with TRUNCATE+INSERT pattern"
```

---

## Task 4: Configuración y orquestación

**Files:**
- Modify: `config.py` — agregar entrada en `ENTITIES_CONFIG`
- Modify: `main.py` — agregar ramas de extracción y carga

- [ ] **Step 1: Agregar `contact_lists` en `ENTITIES_CONFIG` en `config.py`**

Agregar al final del dict `ENTITIES_CONFIG` (antes del cierre `}`):

```python
"contact_lists": {
    "enabled": True,
    "filter_id": None,
    "table_name": "freshsale.contact_lists",
    "incremental": False,  # Carga completa siempre (tabla puente sin updated_at)
    "date_field": None
},
```

- [ ] **Step 2: Agregar rama de extracción en `main.py`**

En el bloque `elif` de extracción (alrededor de línea 190, después de `elif entity_name == "teams":`), agregar:

```python
elif entity_name == "contact_lists":
    data = extractor.extract_contact_lists()
```

- [ ] **Step 3: Agregar rama de carga en `main.py`**

En el bloque `elif` de carga (alrededor de línea 242, después de `elif entity_name == "teams":`), agregar:

```python
elif entity_name == "contact_lists":
    load_stats = loader_ext.upsert_contact_lists(loader, data)
```

- [ ] **Step 4: Verificar que `contact_lists` NO quede en `RECONCILABLE_ENTITIES`**

Buscar en `main.py` la definición de `RECONCILABLE_ENTITIES` (alrededor de línea 257) y confirmar que `"contact_lists"` no está en ese set. Es una tabla puente — no necesita reconciliación.

- [ ] **Step 5: Verificar sintaxis general**

```bash
cd /Users/felix/FreshSale_Movigoo && source venv/bin/activate && python -c "import main; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add config.py main.py
git commit -m "feat: wire contact_lists entity into ETL orchestration"
```

---

## Task 5: Prueba end-to-end

**Files:** ninguno — solo ejecución

- [ ] **Step 1: Correr solo la entidad `contact_lists`**

```bash
cd /Users/felix/FreshSale_Movigoo && source venv/bin/activate && python main.py --entity contact_lists --full
```
Expected: logs mostrando extracción de listas, luego contactos por lista, luego INSERT en SQL Server. Sin errores.

- [ ] **Step 2: Verificar datos en SQL Server**

```bash
cd /Users/felix/FreshSale_Movigoo && source venv/bin/activate && python -c "
from etl.sql_loader import SQLServerLoader
import os; from dotenv import load_dotenv; load_dotenv()
from config import SQL_SERVER_CONNECTION_PARAMS
loader = SQLServerLoader(**SQL_SERVER_CONNECTION_PARAMS)
cur = loader.connection.cursor()
cur.execute('SELECT COUNT(*) FROM freshsale.contact_lists')
print('Total rows:', cur.fetchone()[0])
cur.execute('SELECT TOP 5 contact_id, list_id, list_name FROM freshsale.contact_lists')
for row in cur.fetchall():
    print(row)
cur.close()
loader.connection.close()
"
```
Expected: conteo > 0 y 5 filas de muestra con datos reales.

- [ ] **Step 3: Commit final si todo está bien**

```bash
git add -A
git commit -m "feat: contact_lists ETL complete - extracts contact-list membership from Freshsales"
```
