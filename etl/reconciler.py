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
