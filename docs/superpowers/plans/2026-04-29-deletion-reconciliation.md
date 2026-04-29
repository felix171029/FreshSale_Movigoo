# Deletion Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every ETL run (incremental or full), detect and physically DELETE from SQL Server any record that no longer exists in Freshsales.

**Architecture:** Add a `extract_all_ids()` method to `FreshsaleExtractor` that paginates each entity's endpoint collecting only IDs (no `updated_at` filter). A new `etl/reconciler.py` module compares those IDs against SQL Server and issues a DELETE for missing records. `main.py` calls this after every entity upsert. For `deals`, deal_products are cascade-deleted. Safety guard: if Freshsales returns 0 IDs the reconciliation is skipped to avoid wiping the table on API failure.

**Tech Stack:** Python 3, pymssql, existing Freshsales REST API endpoints (same auth/pagination already in use)

---

## File Map

| File | Change |
|---|---|
| `etl/freshsale_extractor.py` | Add `extract_all_ids()` method |
| `etl/reconciler.py` | **New file** — `reconcile_deletions()` function |
| `main.py` | Remove early-return on empty data; add reconciliation phase; update stats/logs |

---

## Task 1: Add `extract_all_ids()` to FreshsaleExtractor

**Files:**
- Modify: `etl/freshsale_extractor.py` (after `extract_deal_prediction_choices`, before `extract_deal_products`)

- [ ] **Step 1: Agregar el método al final de la clase (antes de `extract_deal_products`)**

Buscar la línea `def extract_deal_products(self, deal_id: int)` e insertar el siguiente método justo antes:

```python
def extract_all_ids(self, entity_name: str, filter_id: Optional[int] = None,
                    extra_filter_ids: Optional[List[int]] = None) -> Optional[set]:
    """
    Pagina el endpoint de la entidad sin filtro de fecha y devuelve el set de todos
    los IDs activos. Usado para reconciliación de eliminaciones.
    Devuelve None si alguna página falla (señal para NO reconciliar).
    """
    # Mapa: entity_name -> (path_template, clave en la respuesta JSON)
    entity_map = {
        "deals":            ("deals/view/{filter_id}", "deals"),
        "contacts":         ("contacts/view/{filter_id}", "contacts"),
        "sales_accounts":   ("sales_accounts/view/{filter_id}", "sales_accounts"),
        "leads":            ("leads/view/{filter_id}", "leads"),
        "tasks":            ("tasks", "tasks"),
        "appointments":     ("appointments", "appointments"),
        "sales_activities": ("sales_activities", "sales_activities"),
        "products":         ("cpq/products", "products"),
    }

    if entity_name not in entity_map:
        return None

    path_template, record_key = entity_map[entity_name]

    if "{filter_id}" in path_template:
        all_filter_ids = [filter_id] + (extra_filter_ids or [])
    else:
        all_filter_ids = [None]

    active_ids = set()

    for fid in all_filter_ids:
        path = path_template.replace("{filter_id}", str(fid)) if fid is not None else path_template
        url = f"{self.base_url}/{path}"
        page = 1
        total_pages = None

        while True:
            params = {"page": page, "per_page": self.page_size}
            data = self._make_request(url, params)

            if data is None:
                logger.warning(f"ID sweep failed for {entity_name} page {page}"
                               + (f" filter {fid}" if fid else ""))
                return None  # API failure — caller must skip reconciliation

            records = data.get(record_key, [])
            meta = data.get("meta", {})

            for record in records:
                if record.get("id"):
                    active_ids.add(record["id"])

            if total_pages is None:
                total_pages = meta.get("total_pages", 1)

            if page >= total_pages or len(records) == 0:
                break

            page += 1

    logger.info(f"ID sweep {entity_name}: {len(active_ids)} active IDs in Freshsales")
    return active_ids
```

- [ ] **Step 2: Verificar que el método queda dentro de la clase `FreshsaleExtractor`**

Abrir `etl/freshsale_extractor.py` y confirmar que la indentación del nuevo método es 4 espacios (igual que los demás métodos de la clase).

- [ ] **Step 3: Commit**

```bash
cd /Users/felix/FreshSale_Movigoo
git add etl/freshsale_extractor.py
git commit -m "feat: add extract_all_ids() for deletion reconciliation sweep"
```

---

## Task 2: Crear `etl/reconciler.py`

**Files:**
- Create: `etl/reconciler.py`

- [ ] **Step 1: Crear el archivo**

```python
"""
Reconciliación de eliminaciones: detecta y borra físicamente registros que ya
no existen en Freshsales comparando IDs activos vs IDs en SQL Server.
"""

import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)


def reconcile_deletions(loader, entity_name: str, table_name: str,
                        active_ids: Set[int]) -> int:
    """
    Borra de `table_name` todos los registros cuyo `id` no esté en `active_ids`.

    Guardia de seguridad: si `active_ids` está vacío, salta la operación con
    un warning (evita borrar toda la tabla por un fallo de la API).

    Para 'deals' también borra en cascada los deal_products asociados.

    Returns:
        Número de filas eliminadas de la tabla principal.
    """
    if not active_ids:
        logger.warning(
            f"Reconcile SKIPPED for {entity_name}: "
            "Freshsales devolvió 0 IDs activos (guardia de seguridad)"
        )
        return 0

    cursor = loader.connection.cursor()
    deleted = 0

    try:
        # Obtener todos los IDs actuales en SQL Server
        cursor.execute(f"SELECT id FROM {table_name}")
        sql_ids = {row[0] for row in cursor.fetchall()}

        ids_to_delete = sql_ids - active_ids

        if not ids_to_delete:
            logger.info(f"Reconcile {entity_name}: sin eliminaciones pendientes")
            return 0

        logger.info(
            f"Reconcile {entity_name}: {len(ids_to_delete)} registros a eliminar "
            f"(en SQL={len(sql_ids)}, en Freshsales={len(active_ids)})"
        )

        # Insertar IDs a borrar en tabla temporal para evitar límites de parámetros
        cursor.execute("CREATE TABLE #ids_to_delete (id BIGINT NOT NULL)")
        values_sql = ", ".join(f"({id_val})" for id_val in ids_to_delete)
        cursor.execute(f"INSERT INTO #ids_to_delete (id) VALUES {values_sql}")

        # Cascada: borrar deal_products antes que deals
        if entity_name == "deals":
            cursor.execute("""
                DELETE FROM freshsale.deal_products
                WHERE deal_id IN (SELECT id FROM #ids_to_delete)
            """)
            dp_deleted = cursor.rowcount
            logger.info(f"Reconcile deal_products (cascada): {dp_deleted} filas eliminadas")

        # Borrar de la tabla principal
        cursor.execute(
            f"DELETE FROM {table_name} WHERE id IN (SELECT id FROM #ids_to_delete)"
        )
        deleted = cursor.rowcount

        loader.connection.commit()
        logger.info(f"Reconcile {entity_name}: {deleted} filas eliminadas de {table_name}")

        return deleted

    except Exception as e:
        loader.connection.rollback()
        logger.error(f"Reconcile falló para {entity_name}: {str(e)}", exc_info=True)
        return 0

    finally:
        cursor.close()
```

- [ ] **Step 2: Commit**

```bash
git add etl/reconciler.py
git commit -m "feat: add reconciler module for physical deletion detection"
```

---

## Task 3: Conectar reconciliación en `main.py`

**Files:**
- Modify: `main.py`

Este task requiere 4 cambios en `main.py`.

### Cambio A — Import del reconciler (línea ~83, junto a los otros imports de etl)

- [ ] **Step 1: Agregar import**

Buscar la línea:
```python
from etl.sp_runner import run_stored_procedures
```
Agregar justo debajo:
```python
from etl.reconciler import reconcile_deletions
```

### Cambio B — Agregar `"deleted": 0` al dict de stats (línea ~129)

- [ ] **Step 2: Actualizar stats dict**

Buscar:
```python
    stats = {
        "extracted": 0,
        "inserted": 0,
        "updated": 0,
        "failed": 0,
        "duration": 0,
        "status": "SUCCESS"
    }
```
Reemplazar con:
```python
    stats = {
        "extracted": 0,
        "inserted": 0,
        "updated": 0,
        "deleted": 0,
        "failed": 0,
        "duration": 0,
        "status": "SUCCESS"
    }
```

### Cambio C — Reestructurar el bloque de carga y agregar reconciliación

El bloque actual tiene un early-return en `if not data` que impide que la reconciliación corra cuando no hay cambios en un run incremental. Hay que eliminar ese early-return y envolver la sección de carga en `if data:`.

- [ ] **Step 3: Reemplazar la sección desde `stats["extracted"]` hasta el final del bloque de carga**

Buscar este bloque (aprox. líneas 194–257):
```python
        stats["extracted"] = len(data)

        if not data:
            logger.info(f"No data to load for {entity_name}")
            stats["duration"] = int(time.time() - start_time)
            return stats

        # CARGA
        logger.info(f"Loading {len(data)} records to SQL Server...")

        if entity_name == "deals":
```

Reemplazar con:
```python
        stats["extracted"] = len(data)

        # CARGA
        if data:
            logger.info(f"Loading {len(data)} records to SQL Server...")

            if entity_name == "deals":
```

**IMPORTANTE:** Todo el bloque de if/elif de carga (deals, contacts, leads, sales_accounts, tasks, appointments, sales_activities, products, pipelines, stages, forecast_categories, deal_predictions, users, teams) debe quedar **indentado un nivel más** (12 espacios en lugar de 8) porque ahora está dentro del `if data:`. Al final del bloque `if data:` el código queda así:

```python
            stats["inserted"] = load_stats.get("inserted", 0)
            stats["updated"] = load_stats.get("updated", 0)
            stats["failed"] = load_stats.get("failed", 0)

        else:
            logger.info(f"No records to upsert for {entity_name} (incremental: nothing changed)")
```

### Cambio D — Agregar bloque de reconciliación después del bloque de carga

- [ ] **Step 4: Agregar reconciliación después del bloque `if data: ... else: ...`**

Justo después del bloque `else: logger.info(...)` y antes de `# Calcular duración`, agregar:

```python
        # RECONCILIACIÓN — detectar y eliminar registros borrados en Freshsales
        table_name = config.get("table_name")
        if table_name:
            if config.get("incremental"):
                # Incremental: los datos traídos son parciales, necesitamos barrido completo de IDs
                extra_ids = [28006328833, 28006328834, 28006328835, 28006328836] \
                    if entity_name == "deals" else None
                active_ids = extractor.extract_all_ids(entity_name, filter_id, extra_ids)
            else:
                # No-incremental: ya tenemos todos los registros en `data`
                # Si data está vacío probablemente fue un fallo de API — no reconciliar
                active_ids = {r["id"] for r in data if r.get("id")} if data else None

            if active_ids is not None:
                deleted_count = reconcile_deletions(loader, entity_name, table_name, active_ids)
                stats["deleted"] = deleted_count
```

### Cambio E — Actualizar overall_stats y log final

- [ ] **Step 5: Agregar `total_deleted` a overall_stats**

Buscar en `main()`:
```python
    overall_stats = {
        "total_extracted": 0,
        "total_inserted": 0,
        "total_updated": 0,
        "total_failed": 0,
        "entities_processed": 0,
        "entities_failed": 0
    }
```
Reemplazar con:
```python
    overall_stats = {
        "total_extracted": 0,
        "total_inserted": 0,
        "total_updated": 0,
        "total_deleted": 0,
        "total_failed": 0,
        "entities_processed": 0,
        "entities_failed": 0
    }
```

- [ ] **Step 6: Acumular deleted en el loop de entidades**

Buscar:
```python
            overall_stats["total_updated"] += stats.get("updated", 0)
            overall_stats["total_failed"] += stats.get("failed", 0)
```
Reemplazar con:
```python
            overall_stats["total_updated"] += stats.get("updated", 0)
            overall_stats["total_deleted"] += stats.get("deleted", 0)
            overall_stats["total_failed"] += stats.get("failed", 0)
```

- [ ] **Step 7: Agregar deleted al log final**

Buscar:
```python
        logger.info(f"Total records updated: {overall_stats['total_updated']}")
        logger.info(f"Total records failed: {overall_stats['total_failed']}")
```
Reemplazar con:
```python
        logger.info(f"Total records updated: {overall_stats['total_updated']}")
        logger.info(f"Total records deleted: {overall_stats['total_deleted']}")
        logger.info(f"Total records failed: {overall_stats['total_failed']}")
```

- [ ] **Step 8: Commit final**

```bash
git add main.py
git commit -m "feat: wire deletion reconciliation into every ETL run"
```

---

## Verificación manual post-implementación

- [ ] Correr el ETL en modo incremental y confirmar en los logs que aparece la línea `ID sweep <entity>: N active IDs in Freshsales` para cada entidad incremental
- [ ] Borrar un deal de prueba en Freshsales, correr `python main.py`, verificar que el deal ya no aparece en `SELECT * FROM freshsale.deals WHERE id = <id_borrado>`
- [ ] Verificar que los `deal_products` del deal borrado también desaparecieron
- [ ] Confirmar en los logs que aparece `Reconcile deals: X filas eliminadas`
