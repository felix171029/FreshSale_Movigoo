#!/usr/bin/env python3
"""
ETL Principal: Freshsale -> SQL Server

Este script extrae todos los datos de Freshsale y los carga en SQL Server.
Soporta carga incremental basada en fecha de última actualización.

Uso:
    python main.py                  # Carga incremental
    python main.py --full           # Carga completa (ignora última ejecución)
    python main.py --entity deals   # Solo carga una entidad específica
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Agregar path para imports
sys.path.append(str(Path(__file__).parent))

from config import (
    FRESHSALE_DOMAIN,
    FRESHSALE_API_KEY,
    PAGE_SIZE,
    MAX_RETRIES,
    RETRY_DELAY,
    REQUEST_TIMEOUT,
    RATE_LIMIT_DELAY,
    SQL_SERVER_CONNECTION_STRING,
    ENTITIES_CONFIG,
    LOG_LEVEL,
    LOG_FILE,
    LOG_FORMAT
)

from etl.freshsale_extractor import FreshsaleExtractor
from etl.sql_loader import SQLServerLoader
import etl.sql_loader_extended as loader_ext


# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def setup_database(loader: SQLServerLoader) -> bool:
    """
    Ejecuta el script de creación de esquema

    Args:
        loader: Instancia de SQLServerLoader

    Returns:
        True si fue exitoso
    """
    logger.info("Setting up database schema...")

    script_path = Path(__file__).parent / "sql" / "01_create_schema.sql"

    if not script_path.exists():
        logger.error(f"Schema script not found: {script_path}")
        return False

    return loader.execute_script_file(str(script_path))


def process_entity(entity_name: str, config: dict, extractor: FreshsaleExtractor,
                   loader: SQLServerLoader, force_full_load: bool = False) -> dict:
    """
    Procesa una entidad completa: extrae, transforma y carga

    Args:
        entity_name: Nombre de la entidad
        config: Configuración de la entidad
        extractor: Instancia de FreshsaleExtractor
        loader: Instancia de SQLServerLoader
        force_full_load: True para forzar carga completa

    Returns:
        Diccionario con estadísticas del proceso
    """
    start_time = time.time()
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing entity: {entity_name}")
    logger.info(f"{'='*80}")

    stats = {
        "extracted": 0,
        "inserted": 0,
        "updated": 0,
        "failed": 0,
        "duration": 0,
        "status": "SUCCESS"
    }

    try:
        # Determinar si es carga incremental
        last_updated = None
        if config.get("incremental") and not force_full_load:
            last_updated = loader.get_last_extraction_date(entity_name)
            if last_updated:
                logger.info(f"Incremental load since: {last_updated}")
            else:
                logger.info("First time load - extracting all records")
        else:
            logger.info("Full load - extracting all records")

        # EXTRACCIÓN
        data = []
        filter_id = config.get("filter_id")

        if entity_name == "deals":
            data = extractor.extract_deals(filter_id, last_updated)
        elif entity_name == "contacts":
            data = extractor.extract_contacts(filter_id, last_updated)
        elif entity_name == "leads":
            data = extractor.extract_leads(filter_id, last_updated)
        elif entity_name == "sales_accounts":
            data = extractor.extract_sales_accounts(filter_id, last_updated)
        elif entity_name == "tasks":
            data = extractor.extract_tasks(last_updated)
        elif entity_name == "appointments":
            data = extractor.extract_appointments(last_updated)
        elif entity_name == "sales_activities":
            data = extractor.extract_sales_activities(last_updated)
        elif entity_name == "products":
            data = extractor.extract_products(last_updated)
        elif entity_name == "pipelines":
            data = extractor.extract_pipelines()
        elif entity_name == "stages":
            # Extraer stages de todos los pipelines (ya vienen incluidos en la respuesta de pipelines)
            pipelines = extractor.extract_pipelines()
            data = []
            for pipeline in pipelines:
                # Los stages ya vienen en el campo deal_stages de cada pipeline
                stages = pipeline.get("deal_stages", [])
                data.extend(stages)
        elif entity_name == "forecast_categories":
            data = extractor.extract_deal_fields()
        elif entity_name == "deal_predictions":
            data = extractor.extract_deal_prediction_choices()
        elif entity_name == "users":
            data = extractor.extract_users()
        elif entity_name == "teams":
            data = extractor.extract_teams()
        else:
            logger.warning(f"Unknown entity type: {entity_name}")
            return stats

        stats["extracted"] = len(data)

        if not data:
            logger.info(f"No data to load for {entity_name}")
            stats["duration"] = int(time.time() - start_time)
            return stats

        # CARGA
        logger.info(f"Loading {len(data)} records to SQL Server...")

        if entity_name == "deals":
            load_stats = loader.upsert_deals(data)
        elif entity_name == "contacts":
            load_stats = loader_ext.upsert_contacts(loader, data)
        elif entity_name == "leads":
            load_stats = loader_ext.upsert_leads(loader, data)
        elif entity_name == "sales_accounts":
            load_stats = loader_ext.upsert_sales_accounts(loader, data)
        elif entity_name == "tasks":
            load_stats = loader_ext.upsert_tasks(loader, data)
        elif entity_name == "appointments":
            load_stats = loader_ext.upsert_appointments(loader, data)
        elif entity_name == "sales_activities":
            load_stats = loader_ext.upsert_sales_activities(loader, data)
        elif entity_name == "products":
            load_stats = loader_ext.upsert_products(loader, data)
        elif entity_name == "pipelines":
            load_stats = loader_ext.upsert_pipelines(loader, data)
        elif entity_name == "stages":
            load_stats = loader_ext.upsert_stages(loader, data)
        elif entity_name == "forecast_categories":
            load_stats = loader_ext.upsert_forecast_categories(loader, data)
        elif entity_name == "deal_predictions":
            load_stats = loader_ext.upsert_deal_predictions(loader, data)
        elif entity_name == "users":
            load_stats = loader.upsert_users(data)
        elif entity_name == "teams":
            load_stats = loader.upsert_teams(data)
        else:
            logger.warning(f"No loader implemented for: {entity_name}")
            load_stats = {"inserted": 0, "updated": 0, "failed": 0}

        stats["inserted"] = load_stats.get("inserted", 0)
        stats["updated"] = load_stats.get("updated", 0)
        stats["failed"] = load_stats.get("failed", 0)

        # Calcular duración
        stats["duration"] = int(time.time() - start_time)

        logger.info(f"Entity {entity_name} processed successfully in {stats['duration']} seconds")

        return stats

    except Exception as e:
        logger.error(f"Failed to process entity {entity_name}: {str(e)}", exc_info=True)
        stats["status"] = "ERROR"
        stats["error"] = str(e)
        stats["duration"] = int(time.time() - start_time)
        return stats


def main():
    """Función principal del ETL"""
    parser = argparse.ArgumentParser(description="ETL Freshsale -> SQL Server")
    parser.add_argument("--full", action="store_true", help="Force full load (ignore last execution)")
    parser.add_argument("--entity", type=str, help="Process only specific entity")
    parser.add_argument("--skip-schema", action="store_true", help="Skip schema setup")

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("ETL FRESHSALE -> SQL SERVER")
    logger.info("="*80)
    logger.info(f"Started at: {datetime.now()}")
    logger.info(f"Mode: {'FULL LOAD' if args.full else 'INCREMENTAL LOAD'}")
    logger.info("="*80)

    total_start_time = time.time()
    overall_stats = {
        "total_extracted": 0,
        "total_inserted": 0,
        "total_updated": 0,
        "total_failed": 0,
        "entities_processed": 0,
        "entities_failed": 0
    }

    # Inicializar extractor
    logger.info("Initializing Freshsale extractor...")
    extractor = FreshsaleExtractor(
        domain=FRESHSALE_DOMAIN,
        api_key=FRESHSALE_API_KEY,
        page_size=PAGE_SIZE,
        max_retries=MAX_RETRIES,
        retry_delay=RETRY_DELAY,
        request_timeout=REQUEST_TIMEOUT,
        rate_limit_delay=RATE_LIMIT_DELAY
    )

    # Inicializar loader
    logger.info("Initializing SQL Server loader...")
    loader = SQLServerLoader(SQL_SERVER_CONNECTION_STRING)

    if not loader.connect():
        logger.error("Failed to connect to SQL Server. Aborting.")
        sys.exit(1)

    try:
        # Setup de base de datos (crear tablas si no existen)
        if not args.skip_schema:
            if not setup_database(loader):
                logger.error("Failed to setup database schema. Aborting.")
                sys.exit(1)

        # Determinar entidades a procesar
        entities_to_process = {}

        if args.entity:
            # Solo procesar la entidad especificada
            if args.entity in ENTITIES_CONFIG:
                entities_to_process[args.entity] = ENTITIES_CONFIG[args.entity]
            else:
                logger.error(f"Unknown entity: {args.entity}")
                sys.exit(1)
        else:
            # Procesar todas las entidades habilitadas
            entities_to_process = {
                name: config
                for name, config in ENTITIES_CONFIG.items()
                if config.get("enabled", False)
            }

        # Procesar cada entidad
        for entity_name, entity_config in entities_to_process.items():
            logger.info(f"\nProcessing: {entity_name}")

            stats = process_entity(
                entity_name,
                entity_config,
                extractor,
                loader,
                force_full_load=args.full
            )

            # Registrar ejecución
            loader.log_etl_execution(
                entity_name=entity_name,
                status=stats.get("status", "SUCCESS"),
                records_extracted=stats.get("extracted", 0),
                records_inserted=stats.get("inserted", 0),
                records_updated=stats.get("updated", 0),
                records_failed=stats.get("failed", 0),
                error_message=stats.get("error"),
                duration_seconds=stats.get("duration", 0)
            )

            # Actualizar estadísticas globales
            overall_stats["total_extracted"] += stats.get("extracted", 0)
            overall_stats["total_inserted"] += stats.get("inserted", 0)
            overall_stats["total_updated"] += stats.get("updated", 0)
            overall_stats["total_failed"] += stats.get("failed", 0)

            if stats.get("status") == "SUCCESS":
                overall_stats["entities_processed"] += 1
            else:
                overall_stats["entities_failed"] += 1

        # Resumen final
        total_duration = int(time.time() - total_start_time)

        logger.info("\n" + "="*80)
        logger.info("ETL COMPLETED")
        logger.info("="*80)
        logger.info(f"Total duration: {total_duration} seconds")
        logger.info(f"Entities processed: {overall_stats['entities_processed']}")
        logger.info(f"Entities failed: {overall_stats['entities_failed']}")
        logger.info(f"Total records extracted: {overall_stats['total_extracted']}")
        logger.info(f"Total records inserted: {overall_stats['total_inserted']}")
        logger.info(f"Total records updated: {overall_stats['total_updated']}")
        logger.info(f"Total records failed: {overall_stats['total_failed']}")
        logger.info("="*80)

        # Estadísticas del extractor
        extractor_stats = extractor.get_stats()
        logger.info(f"API requests made: {extractor_stats['total_requests']}")
        logger.info(f"API requests failed: {extractor_stats['failed_requests']}")

    except Exception as e:
        logger.error(f"ETL failed with error: {str(e)}", exc_info=True)
        sys.exit(1)

    finally:
        loader.disconnect()

    logger.info(f"Finished at: {datetime.now()}")

    # Exit code basado en resultados
    if overall_stats["entities_failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
