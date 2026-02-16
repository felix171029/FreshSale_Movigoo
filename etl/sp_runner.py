"""
Módulo para ejecutar Stored Procedures y registrar auditoría en etl_control.

Uso:
    from etl.sp_runner import run_stored_procedures

    STORED_PROCEDURES = [
        "dbo.act_fact_deals_products",
        # Agregar más SPs aquí
    ]

    run_stored_procedures(loader, STORED_PROCEDURES)
"""

import logging
import time
from typing import List

logger = logging.getLogger(__name__)


def execute_sp(loader, sp_name: str) -> dict:
    """
    Ejecuta un stored procedure y registra la auditoría en etl_control.

    Args:
        loader: Instancia de SQLServerLoader con conexión activa
        sp_name: Nombre del SP (ej. 'dbo.act_fact_deals_products')

    Returns:
        dict con keys: status, duration, error
    """
    start_time = time.time()
    result = {
        "sp_name": sp_name,
        "status": "SUCCESS",
        "duration": 0,
        "error": None,
    }

    logger.info(f"\n{'='*80}")
    logger.info(f"Executing stored procedure: {sp_name}")
    logger.info(f"{'='*80}")

    try:
        cursor = loader.connection.cursor()
        cursor.execute(f"EXEC {sp_name}")
        loader.connection.commit()
        cursor.close()

        result["duration"] = int(time.time() - start_time)
        logger.info(f"SP {sp_name} completed successfully in {result['duration']}s")

    except Exception as e:
        loader.connection.rollback()
        result["status"] = "ERROR"
        result["error"] = str(e)
        result["duration"] = int(time.time() - start_time)
        logger.error(f"SP {sp_name} failed: {e}", exc_info=True)

    finally:
        # Auditoría en etl_control usando entity_name = nombre del SP
        loader.log_etl_execution(
            entity_name=sp_name,
            status=result["status"],
            records_extracted=0,
            records_inserted=0,
            records_updated=0,
            records_failed=0,
            error_message=result["error"],
            duration_seconds=result["duration"],
        )

    return result


def run_stored_procedures(loader, sp_list: List[str]) -> dict:
    """
    Ejecuta una lista de stored procedures secuencialmente y registra cada uno en etl_control.

    Args:
        loader: Instancia de SQLServerLoader con conexión activa
        sp_list: Lista de nombres de SPs a ejecutar

    Returns:
        dict con resumen: total, success, failed, results
    """
    summary = {
        "total": len(sp_list),
        "success": 0,
        "failed": 0,
        "results": [],
    }

    for sp_name in sp_list:
        result = execute_sp(loader, sp_name)
        summary["results"].append(result)

        if result["status"] == "SUCCESS":
            summary["success"] += 1
        else:
            summary["failed"] += 1

    logger.info(f"\nStored Procedures summary: {summary['success']}/{summary['total']} OK, {summary['failed']} failed")
    return summary
