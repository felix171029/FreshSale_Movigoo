"""
Configuración del ETL Freshsale -> SQL Server
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ================================================================
# CONFIGURACIÓN DE FRESHSALE
# ================================================================
FRESHSALE_DOMAIN = os.getenv("FRESHSALE_DOMAIN")
FRESHSALE_API_KEY = os.getenv("FRESHSALE_API_KEY")
FRESHSALE_BASE_URL = f"https://{FRESHSALE_DOMAIN}/crm/sales/api"

# Configuración de paginación y rate limiting
PAGE_SIZE = 100  # Número de registros por página
MAX_RETRIES = 3  # Número máximo de reintentos en caso de error
RETRY_DELAY = 5  # Segundos entre reintentos
REQUEST_TIMEOUT = 30  # Timeout para requests en segundos
RATE_LIMIT_DELAY = 0.5  # Delay entre requests para evitar rate limiting

# ================================================================
# CONFIGURACIÓN DE SQL SERVER
# ================================================================
SQL_SERVER_HOST = os.getenv("REP_DB_HOST")
SQL_SERVER_PORT = int(os.getenv("REP_DB_PORT", "1433"))
SQL_SERVER_DATABASE = os.getenv("REP_DB_NAME")
SQL_SERVER_USER = os.getenv("REP_DB_USER")
SQL_SERVER_PASSWORD = os.getenv("REP_DB_PASSWORD")

# Parámetros de conexión para pymssql
SQL_SERVER_CONNECTION_PARAMS = {
    "server": SQL_SERVER_HOST,
    "port": SQL_SERVER_PORT,
    "database": SQL_SERVER_DATABASE,
    "user": SQL_SERVER_USER,
    "password": SQL_SERVER_PASSWORD,
    "tds_version": "7.4",
    "login_timeout": 60,
}

# ================================================================
# CONFIGURACIÓN DE LOGGING
# ================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "etl_freshsale.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ================================================================
# CONFIGURACIÓN DE ENTIDADES A EXTRAER
# ================================================================
# Mapeo de entidades y sus filtros
ENTITIES_CONFIG = {
    "deals": {
        "enabled": True,
        "filter_id": 28001560042,  # "All Deals"
        "table_name": "freshsale.deals",
        "incremental": True,
        "date_field": "updated_at"
    },
    "contacts": {
        "enabled": True,
        "filter_id": 28001560030,  # "All Contacts"
        "table_name": "freshsale.contacts",
        "incremental": True,
        "date_field": "updated_at"
    },
    "leads": {
        "enabled": False,  # Deshabilitado por permisos
        "filter_id": 28001560014,  # "My Leads"
        "table_name": "freshsale.leads",
        "incremental": True,
        "date_field": "updated_at"
    },
    "sales_accounts": {
        "enabled": True,
        "filter_id": 28001560057,  # "All Accounts"
        "table_name": "freshsale.sales_accounts",
        "incremental": True,
        "date_field": "updated_at"
    },
    "tasks": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.tasks",
        "incremental": True,
        "date_field": "updated_at"
    },
    "appointments": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.appointments",
        "incremental": True,
        "date_field": "updated_at"
    },
    "sales_activities": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.sales_activities",
        "incremental": True,
        "date_field": "updated_at"
    },
    "users": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.users",
        "incremental": False,  # Carga completa siempre
        "date_field": None
    },
    "teams": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.teams",
        "incremental": False,  # Carga completa siempre
        "date_field": None
    },
    "leads": {
        "enabled": False,  # Deshabilitado: API key sin permisos de acceso (403 Access Denied)
        "filter_id": 28001560017,  # "All Leads"
        "table_name": "freshsale.leads",
        "incremental": True,
        "date_field": "updated_at"
    },
    "pipelines": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.pipelines",
        "incremental": False,  # Carga completa siempre
        "date_field": None
    },
    "stages": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.stages",
        "incremental": False,  # Carga completa siempre
        "date_field": None
    },
    "products": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.products",
        "incremental": True,
        "date_field": "updated_at"
    },
    "forecast_categories": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.forecast_categories",
        "incremental": False,  # Carga completa siempre (son pocos registros)
        "date_field": None
    },
    "deal_predictions": {
        "enabled": True,
        "filter_id": None,  # No usa filtros
        "table_name": "freshsale.deal_predictions",
        "incremental": False,  # Carga completa siempre (son pocos registros)
        "date_field": None
    }
}
