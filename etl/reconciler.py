"""
Reconciliación de eliminaciones: detecta y borra físicamente registros que ya
no existen en Freshsales comparando IDs activos vs IDs en SQL Server.
"""

import logging
from typing import Dict, Set

from etl.sql_loader import SQLServerLoader

logger = logging.getLogger(__name__)

_ALLOWED_TABLES = {
    "freshsale.deals", "freshsale.contacts", "freshsale.sales_accounts",
    "freshsale.leads", "freshsale.tasks", "freshsale.appointments",
    "freshsale.sales_activities", "freshsale.products", "freshsale.users",
    "freshsale.teams", "freshsale.pipelines", "freshsale.stages",
    "freshsale.forecast_categories", "freshsale.deal_predictions",
}


def reconcile_deletions(loader, entity_name: str, table_name: str,
                        active_ids: Set[int]) -> Dict[str, int]:
    """
    Borra de `table_name` todos los registros cuyo `id` no esté en `active_ids`.

    Guardia de seguridad: si `active_ids` está vacío, salta la operación con
    un warning (evita borrar toda la tabla por un fallo de la API).

    Para 'deals' también borra en cascada los deal_products asociados.

    Returns:
        Dict con claves "deleted" y "cascade_deleted" indicando filas eliminadas.
    """
    if not active_ids:
        logger.warning(
            f"Reconcile SKIPPED for {entity_name}: "
            "Freshsales devolvió 0 IDs activos (guardia de seguridad)"
        )
        return {"deleted": 0, "cascade_deleted": 0}

    if table_name not in _ALLOWED_TABLES:
        logger.error(f"Reconcile rechazado: tabla '{table_name}' no está en la lista permitida")
        return {"deleted": 0, "cascade_deleted": 0}

    cursor = loader.connection.cursor()
    deleted = 0
    cascade_deleted = 0

    try:
        # Obtener todos los IDs actuales en SQL Server
        cursor.execute(f"SELECT id FROM {table_name}")
        sql_ids = {row[0] for row in cursor.fetchall()}

        ids_to_delete = sql_ids - active_ids

        if not ids_to_delete:
            logger.info(f"Reconcile {entity_name}: sin eliminaciones pendientes")
            return {"deleted": 0, "cascade_deleted": 0}

        logger.info(
            f"Reconcile {entity_name}: {len(ids_to_delete)} registros a eliminar "
            f"(en SQL={len(sql_ids)}, en Freshsales={len(active_ids)})"
        )

        # Insertar IDs a borrar en tabla temporal para evitar límites de parámetros
        cursor.execute("CREATE TABLE #ids_to_delete (id BIGINT NOT NULL)")
        SQLServerLoader._bulk_insert(cursor, "#ids_to_delete", ["id"], [(id_val,) for id_val in ids_to_delete])

        # Cascada: borrar deal_products antes que deals
        if entity_name == "deals":
            cursor.execute("""
                DELETE FROM freshsale.deal_products
                WHERE deal_id IN (SELECT id FROM #ids_to_delete)
            """)
            cascade_deleted = cursor.rowcount
            logger.info(f"Reconcile deal_products (cascada): {cascade_deleted} filas eliminadas")

        # Borrar de la tabla principal
        cursor.execute(
            f"DELETE FROM {table_name} WHERE id IN (SELECT id FROM #ids_to_delete)"
        )
        deleted = cursor.rowcount

        # Limpiar tabla temporal
        cursor.execute("IF OBJECT_ID('tempdb..#ids_to_delete') IS NOT NULL DROP TABLE #ids_to_delete")

        loader.connection.commit()
        logger.info(f"Reconcile {entity_name}: {deleted} filas eliminadas de {table_name}")

        return {"deleted": deleted, "cascade_deleted": cascade_deleted}

    except Exception as e:
        loader.connection.rollback()
        logger.error(f"Reconcile falló para {entity_name}: {str(e)}", exc_info=True)
        return {"deleted": 0, "cascade_deleted": 0}

    finally:
        cursor.close()
