"""
Módulo de carga de datos a SQL Server
"""

import pymssql
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dateutil import parser as date_parser
import json

logger = logging.getLogger(__name__)


class SQLServerLoader:
    """Carga datos en SQL Server"""

    def __init__(self, connection_params: dict):
        """
        Inicializa el loader de SQL Server

        Args:
            connection_params: Diccionario con parámetros de conexión pymssql
        """
        self.connection_params = connection_params
        self.connection = None
        self.stats = {
            "inserted": 0,
            "updated": 0,
            "failed": 0
        }

    def connect(self):
        """Establece conexión con SQL Server"""
        try:
            logger.info("Connecting to SQL Server...")
            self.connection = pymssql.connect(**self.connection_params)
            self.connection.autocommit(False)
            logger.info("Connected successfully")
            self.ensure_schema_exists()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SQL Server: {str(e)}")
            return False

    def ensure_schema_exists(self):
        """Crea el schema y todas las tablas si no existen, con estructura exacta del servidor"""
        cursor = self.connection.cursor()
        try:
            ddl_statements = [
                # Schema
                "IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'freshsale') EXEC('CREATE SCHEMA freshsale')",

                # etl_control
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.etl_control') AND type = 'U')
                CREATE TABLE freshsale.etl_control (
                    id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    entity_name NVARCHAR(100) NOT NULL,
                    last_execution_date DATETIME NOT NULL,
                    execution_status NVARCHAR(50) NOT NULL,
                    records_extracted INT NULL,
                    records_inserted INT NULL,
                    records_updated INT NULL,
                    records_failed INT NULL,
                    error_message NVARCHAR(MAX) NULL,
                    execution_duration_seconds INT NULL,
                    created_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # etl_log
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.etl_log') AND type = 'U')
                CREATE TABLE freshsale.etl_log (
                    id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    entity_name NVARCHAR(100) NOT NULL,
                    log_level NVARCHAR(20) NOT NULL,
                    message NVARCHAR(MAX) NOT NULL,
                    record_id BIGINT NULL,
                    created_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # users (antes que team_users)
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.users') AND type = 'U')
                CREATE TABLE freshsale.users (
                    id BIGINT NOT NULL PRIMARY KEY,
                    display_name NVARCHAR(500) NULL,
                    email NVARCHAR(200) NULL,
                    is_active BIT NULL DEFAULT 1,
                    work_number NVARCHAR(50) NULL,
                    mobile_number NVARCHAR(50) NULL,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # teams (antes que team_users)
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.teams') AND type = 'U')
                CREATE TABLE freshsale.teams (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(500) NOT NULL,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # team_users (sin FK para coincidir con script.sql)
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.team_users') AND type = 'U')
                CREATE TABLE freshsale.team_users (
                    id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    team_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    CONSTRAINT UQ_team_user UNIQUE (team_id, user_id)
                )""",

                # pipelines (antes que stages)
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.pipelines') AND type = 'U')
                CREATE TABLE freshsale.pipelines (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(500) NOT NULL,
                    is_default BIT NULL DEFAULT 0,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # stages
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.stages') AND type = 'U')
                CREATE TABLE freshsale.stages (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(500) NOT NULL,
                    pipeline_id BIGINT NULL,
                    position BIGINT NULL,
                    probability BIGINT NULL,
                    type NVARCHAR(100) NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # deals (antes que deal_products)
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.deals') AND type = 'U')
                CREATE TABLE freshsale.deals (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(MAX) NOT NULL,
                    amount FLOAT NULL,
                    base_currency_amount FLOAT NULL,
                    expected_close DATE NULL,
                    closed_date DATE NULL,
                    stage_updated_time DATETIME NULL,
                    probability BIGINT NULL,
                    updated_at DATETIME NULL,
                    created_at DATETIME NULL,
                    deal_pipeline_id BIGINT NULL,
                    deal_stage_id BIGINT NULL,
                    age BIGINT NULL,
                    recent_note NVARCHAR(MAX) NULL,
                    expected_deal_value FLOAT NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    forecast_category BIGINT NULL,
                    deal_prediction BIGINT NULL,
                    deal_prediction_last_updated_at DATETIME NULL,
                    has_products BIT NULL DEFAULT 0,
                    rotten_days BIGINT NULL,
                    last_assigned_at DATETIME NULL,
                    sales_account_id BIGINT NULL,
                    cf_pais NVARCHAR(MAX) NULL,
                    cf_integrador NVARCHAR(MAX) NULL,
                    cf_one_time_setup FLOAT NULL,
                    cf_nro_de_meses BIGINT NULL,
                    cf_tipo_de_servicio NVARCHAR(MAX) NULL,
                    cf_explique_prdida NVARCHAR(MAX) NULL,
                    cf_valor_total_de_contrato FLOAT NULL,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE(),
                    last_contacted_sales_activity_mode NVARCHAR(MAX) NULL,
                    last_contacted_via_sales_activity DATETIME NULL,
                    web_form_id BIGINT NULL,
                    upcoming_activities_time DATETIME NULL
                )""",

                # deal_products (sin FK a deals para coincidir con script.sql)
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.deal_products') AND type = 'U')
                CREATE TABLE freshsale.deal_products (
                    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    deal_id BIGINT NOT NULL,
                    product_id BIGINT NULL,
                    product_name NVARCHAR(500) NULL,
                    quantity FLOAT NULL,
                    unit_price FLOAT NULL,
                    total_price FLOAT NULL,
                    discount FLOAT NULL,
                    description NVARCHAR(MAX) NULL,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE(),
                    freshsale_id BIGINT NULL
                )""",

                # contacts
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND type = 'U')
                CREATE TABLE freshsale.contacts (
                    id BIGINT NOT NULL PRIMARY KEY,
                    first_name NVARCHAR(200) NULL,
                    last_name NVARCHAR(200) NULL,
                    display_name NVARCHAR(500) NULL,
                    email NVARCHAR(200) NULL,
                    mobile_number NVARCHAR(50) NULL,
                    work_number NVARCHAR(50) NULL,
                    job_title NVARCHAR(200) NULL,
                    address NVARCHAR(500) NULL,
                    city NVARCHAR(100) NULL,
                    state NVARCHAR(100) NULL,
                    zipcode NVARCHAR(20) NULL,
                    country NVARCHAR(100) NULL,
                    owner_id BIGINT NULL,
                    sales_account_id BIGINT NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # sales_accounts
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.sales_accounts') AND type = 'U')
                CREATE TABLE freshsale.sales_accounts (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(500) NOT NULL,
                    address NVARCHAR(500) NULL,
                    city NVARCHAR(100) NULL,
                    state NVARCHAR(100) NULL,
                    zipcode NVARCHAR(20) NULL,
                    country NVARCHAR(100) NULL,
                    industry_type_id BIGINT NULL,
                    business_type_id BIGINT NULL,
                    number_of_employees BIGINT NULL,
                    annual_revenue FLOAT NULL,
                    website NVARCHAR(500) NULL,
                    phone NVARCHAR(50) NULL,
                    owner_id BIGINT NULL,
                    facebook NVARCHAR(200) NULL,
                    twitter NVARCHAR(200) NULL,
                    linkedin NVARCHAR(200) NULL,
                    territory_id BIGINT NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # leads
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.leads') AND type = 'U')
                CREATE TABLE freshsale.leads (
                    id BIGINT NOT NULL PRIMARY KEY,
                    first_name NVARCHAR(200) NULL,
                    last_name NVARCHAR(200) NULL,
                    display_name NVARCHAR(500) NULL,
                    email NVARCHAR(200) NULL,
                    mobile_number NVARCHAR(50) NULL,
                    work_number NVARCHAR(50) NULL,
                    job_title NVARCHAR(200) NULL,
                    lead_source_id BIGINT NULL,
                    lead_stage_id BIGINT NULL,
                    owner_id BIGINT NULL,
                    company_name NVARCHAR(500) NULL,
                    territory_id BIGINT NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # tasks
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.tasks') AND type = 'U')
                CREATE TABLE freshsale.tasks (
                    id BIGINT NOT NULL PRIMARY KEY,
                    title NVARCHAR(500) NULL,
                    description NVARCHAR(MAX) NULL,
                    due_date DATETIME NULL,
                    status NVARCHAR(50) NULL,
                    owner_id BIGINT NULL,
                    creator_id BIGINT NULL,
                    targetable_type NVARCHAR(100) NULL,
                    targetable_id BIGINT NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    completed_at DATETIME NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # appointments
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.appointments') AND type = 'U')
                CREATE TABLE freshsale.appointments (
                    id BIGINT NOT NULL PRIMARY KEY,
                    title NVARCHAR(500) NULL,
                    description NVARCHAR(MAX) NULL,
                    from_date DATETIME NULL,
                    end_date DATETIME NULL,
                    time_zone NVARCHAR(100) NULL,
                    location NVARCHAR(500) NULL,
                    creator_id BIGINT NULL,
                    owner_id BIGINT NULL,
                    targetable_type NVARCHAR(100) NULL,
                    targetable_id BIGINT NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # sales_activities (columnas según script.sql: notes + activity_type)
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.sales_activities') AND type = 'U')
                CREATE TABLE freshsale.sales_activities (
                    id BIGINT NOT NULL PRIMARY KEY,
                    title NVARCHAR(500) NULL,
                    notes NVARCHAR(MAX) NULL,
                    activity_type NVARCHAR(100) NULL,
                    start_date DATETIME NULL,
                    end_date DATETIME NULL,
                    owner_id BIGINT NULL,
                    creator_id BIGINT NULL,
                    targetable_type NVARCHAR(100) NULL,
                    targetable_id BIGINT NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # products
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.products') AND type = 'U')
                CREATE TABLE freshsale.products (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(500) NOT NULL,
                    category NVARCHAR(255) NULL,
                    description NVARCHAR(MAX) NULL,
                    price FLOAT NULL,
                    currency NVARCHAR(10) NULL,
                    sku_number NVARCHAR(200) NULL,
                    created_at DATETIME NULL,
                    updated_at DATETIME NULL,
                    is_deleted BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # forecast_categories
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.forecast_categories') AND type = 'U')
                CREATE TABLE freshsale.forecast_categories (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(200) NOT NULL,
                    position INT NULL,
                    is_default BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",

                # deal_predictions
                """IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.deal_predictions') AND type = 'U')
                CREATE TABLE freshsale.deal_predictions (
                    id BIGINT NOT NULL PRIMARY KEY,
                    name NVARCHAR(200) NOT NULL,
                    position INT NULL,
                    is_default BIT NULL DEFAULT 0,
                    etl_created_at DATETIME NULL DEFAULT GETDATE(),
                    etl_updated_at DATETIME NULL DEFAULT GETDATE()
                )""",
            ]

            for ddl in ddl_statements:
                try:
                    cursor.execute(ddl)
                except Exception as e:
                    logger.warning(f"DDL warning (puede ignorarse si la tabla ya existe): {str(e)}")

            self.connection.commit()
            logger.info("Schema verificado/creado exitosamente")

        except Exception as e:
            logger.error(f"Error al verificar/crear schema: {str(e)}")
            self.connection.rollback()
        finally:
            cursor.close()

    def disconnect(self):
        """Cierra conexión con SQL Server"""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from SQL Server")

    @staticmethod
    def parse_date(date_string: Any) -> Optional[datetime]:
        """
        Parsea una fecha desde string a datetime
        Maneja formatos ISO 8601 y otros formatos comunes

        Args:
            date_string: String con la fecha o None

        Returns:
            datetime object o None
        """
        if not date_string:
            return None

        SQL_SERVER_MIN_DATE = datetime(1753, 1, 1)
        SQL_SERVER_MAX_DATE = datetime(9999, 12, 31)

        if isinstance(date_string, datetime):
            dt = date_string
        else:
            try:
                # Intentar parsear fecha ISO 8601 (formato de Freshsale)
                dt = date_parser.parse(str(date_string))
            except:
                try:
                    # Intentar formato simple YYYY-MM-DD
                    dt = datetime.strptime(date_string, '%Y-%m-%d')
                except:
                    logger.warning(f"Could not parse date: {date_string}")
                    return None

        # Remover timezone para compatibilidad con SQL Server DATETIME
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)

        # Truncar microsegundos para compatibilidad con SQL Server DATETIME
        dt = dt.replace(microsecond=0)

        if dt < SQL_SERVER_MIN_DATE or dt > SQL_SERVER_MAX_DATE:
            logger.warning(f"Date out of SQL Server range, setting to None: {date_string}")
            return None

        return dt

    def execute_script_file(self, script_path: str) -> bool:
        """
        Ejecuta un archivo SQL

        Args:
            script_path: Ruta al archivo SQL

        Returns:
            True si fue exitoso, False en caso contrario
        """
        try:
            logger.info(f"Executing SQL script: {script_path}")

            with open(script_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()

            # Dividir por GO
            batches = sql_script.split('\nGO\n')

            cursor = self.connection.cursor()

            for batch in batches:
                batch = batch.strip()
                if batch and not batch.startswith('--'):
                    try:
                        cursor.execute(batch)
                    except Exception as e:
                        # Continuar incluso si hay errores (ej: tabla ya existe)
                        logger.warning(f"Batch execution warning: {str(e)}")

            self.connection.commit()
            cursor.close()

            logger.info(f"SQL script executed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to execute SQL script: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False

    def log_etl_execution(self, entity_name: str, status: str, records_extracted: int = 0,
                          records_inserted: int = 0, records_updated: int = 0,
                          records_failed: int = 0, error_message: str = None,
                          duration_seconds: int = 0):
        """
        Registra la ejecución del ETL en la tabla de control

        Args:
            entity_name: Nombre de la entidad
            status: Estado de la ejecución (SUCCESS, ERROR, RUNNING)
            records_extracted: Cantidad de registros extraídos
            records_inserted: Cantidad de registros insertados
            records_updated: Cantidad de registros actualizados
            records_failed: Cantidad de registros fallidos
            error_message: Mensaje de error si aplica
            duration_seconds: Duración de la ejecución en segundos
        """
        try:
            cursor = self.connection.cursor()

            sql = """
                INSERT INTO freshsale.etl_control
                (entity_name, last_execution_date, execution_status, records_extracted,
                 records_inserted, records_updated, records_failed, error_message,
                 execution_duration_seconds)
                VALUES (%s, CAST(GETDATE() AT TIME ZONE 'UTC' AT TIME ZONE 'Pacific SA Standard Time' AS DATETIME), %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(sql, (
                entity_name, status, records_extracted, records_inserted,
                records_updated, records_failed, error_message, duration_seconds
            ))

            self.connection.commit()
            cursor.close()

        except Exception as e:
            logger.error(f"Failed to log ETL execution: {str(e)}")
            if self.connection:
                self.connection.rollback()

    def get_last_extraction_date(self, entity_name: str) -> Optional[datetime]:
        """
        Obtiene la fecha de la última extracción exitosa

        Args:
            entity_name: Nombre de la entidad

        Returns:
            Fecha de última extracción o None
        """
        try:
            cursor = self.connection.cursor()

            sql = """
                SELECT MAX(last_execution_date)
                FROM freshsale.etl_control
                WHERE entity_name = %s AND execution_status = 'SUCCESS'
            """

            cursor.execute(sql, (entity_name,))
            row = cursor.fetchone()
            cursor.close()

            if row and row[0]:
                return row[0]

            return None

        except Exception as e:
            logger.error(f"Failed to get last extraction date: {str(e)}")
            return None

    def upsert_deals(self, deals: List[Dict]) -> Dict[str, int]:
        """Inserta o actualiza deals usando BULK INSERT con tabla temporal"""
        stats = {"inserted": 0, "updated": 0, "failed": 0}

        if not deals:
            logger.info("No deals to load")
            return stats

        cursor = self.connection.cursor()

        try:
            # Crear tabla temporal (mismo orden que tabla real en SQL Server)
            cursor.execute("""
                CREATE TABLE #temp_deals (
                    id BIGINT,
                    name NVARCHAR(2000),
                    amount FLOAT,
                    base_currency_amount FLOAT,
                    expected_close DATE,
                    closed_date DATE,
                    stage_updated_time DATETIME2,
                    probability BIGINT,
                    updated_at DATETIME2,
                    created_at DATETIME2,
                    deal_pipeline_id BIGINT,
                    deal_stage_id BIGINT,
                    age BIGINT,
                    recent_note NVARCHAR(4000),
                    expected_deal_value FLOAT,
                    is_deleted BIT,
                    forecast_category BIGINT,
                    deal_prediction BIGINT,
                    deal_prediction_last_updated_at DATETIME2,
                    has_products BIT,
                    rotten_days BIGINT,
                    last_assigned_at DATETIME2,
                    sales_account_id BIGINT,
                    cf_pais NVARCHAR(200),
                    cf_integrador NVARCHAR(4000),
                    cf_one_time_setup FLOAT,
                    cf_nro_de_meses BIGINT,
                    cf_tipo_de_servicio NVARCHAR(200),
                    cf_explique_prdida NVARCHAR(4000),
                    cf_valor_total_de_contrato FLOAT,
                    last_contacted_sales_activity_mode NVARCHAR(100),
                    last_contacted_via_sales_activity DATETIME2,
                    web_form_id BIGINT,
                    upcoming_activities_time DATETIME2
                )
            """)

            # Preparar datos para bulk insert (mismo orden que tabla temporal)
            insert_data = []
            for deal in deals:
                custom_fields = deal.get("custom_field", {})

                insert_data.append((
                    deal["id"],
                    deal.get("name"),
                    deal.get("amount"),
                    deal.get("base_currency_amount"),
                    self.parse_date(deal.get("expected_close")),
                    self.parse_date(deal.get("closed_date")),
                    self.parse_date(deal.get("stage_updated_time")),
                    deal.get("probability"),
                    self.parse_date(deal.get("updated_at")),
                    self.parse_date(deal.get("created_at")),
                    deal.get("deal_pipeline_id"),
                    deal.get("deal_stage_id"),
                    deal.get("age"),
                    deal.get("recent_note"),
                    deal.get("expected_deal_value"),
                    deal.get("is_deleted", False),
                    deal.get("forecast_category"),
                    deal.get("deal_prediction"),
                    self.parse_date(deal.get("deal_prediction_last_updated_at")),
                    deal.get("has_products", False),
                    deal.get("rotten_days"),
                    self.parse_date(deal.get("last_assigned_at")),
                    deal.get("sales_account_id"),
                    custom_fields.get("cf_pais"),
                    custom_fields.get("cf_integrador"),
                    custom_fields.get("cf_one_time_setup"),
                    custom_fields.get("cf_nro_de_meses"),
                    custom_fields.get("cf_tipo_de_servicio"),
                    custom_fields.get("cf_explique_prdida"),
                    custom_fields.get("cf_valor_total_de_contrato"),
                    deal.get("last_contacted_sales_activity_mode"),
                    self.parse_date(deal.get("last_contacted_via_sales_activity")),
                    deal.get("web_form_id"),
                    self.parse_date(deal.get("upcoming_activities_time"))
                ))

            # Bulk insert: single multi-row INSERT (un solo round-trip)
            self._bulk_insert(cursor, "#temp_deals", [
                "id","name","amount","base_currency_amount","expected_close","closed_date",
                "stage_updated_time","probability","updated_at","created_at","deal_pipeline_id",
                "deal_stage_id","age","recent_note","expected_deal_value","is_deleted",
                "forecast_category","deal_prediction","deal_prediction_last_updated_at",
                "has_products","rotten_days","last_assigned_at","sales_account_id","cf_pais","cf_integrador",
                "cf_one_time_setup","cf_nro_de_meses","cf_tipo_de_servicio","cf_explique_prdida",
                "cf_valor_total_de_contrato","last_contacted_sales_activity_mode",
                "last_contacted_via_sales_activity","web_form_id","upcoming_activities_time"
            ], insert_data)

            # MERGE desde tabla temporal a tabla final
            cursor.execute("""
                MERGE freshsale.deals AS target
                USING #temp_deals AS source ON target.id = source.id
                WHEN MATCHED THEN
                    UPDATE SET
                        name = source.name,
                        amount = source.amount,
                        base_currency_amount = source.base_currency_amount,
                        expected_close = source.expected_close,
                        closed_date = source.closed_date,
                        stage_updated_time = source.stage_updated_time,
                        probability = source.probability,
                        updated_at = source.updated_at,
                        created_at = source.created_at,
                        deal_pipeline_id = source.deal_pipeline_id,
                        deal_stage_id = source.deal_stage_id,
                        age = source.age,
                        recent_note = source.recent_note,
                        expected_deal_value = source.expected_deal_value,
                        is_deleted = source.is_deleted,
                        forecast_category = source.forecast_category,
                        deal_prediction = source.deal_prediction,
                        deal_prediction_last_updated_at = source.deal_prediction_last_updated_at,
                        has_products = source.has_products,
                        rotten_days = source.rotten_days,
                        last_assigned_at = source.last_assigned_at,
                        sales_account_id = source.sales_account_id,
                        last_contacted_sales_activity_mode = source.last_contacted_sales_activity_mode,
                        last_contacted_via_sales_activity = source.last_contacted_via_sales_activity,
                        web_form_id = source.web_form_id,
                        upcoming_activities_time = source.upcoming_activities_time,
                        cf_pais = source.cf_pais,
                        cf_integrador = source.cf_integrador,
                        cf_one_time_setup = source.cf_one_time_setup,
                        cf_nro_de_meses = source.cf_nro_de_meses,
                        cf_tipo_de_servicio = source.cf_tipo_de_servicio,
                        cf_explique_prdida = source.cf_explique_prdida,
                        cf_valor_total_de_contrato = source.cf_valor_total_de_contrato,
                        etl_updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (id, name, amount, base_currency_amount, expected_close,
                            closed_date, stage_updated_time, probability, updated_at,
                            created_at, deal_pipeline_id, deal_stage_id, age,
                            recent_note, expected_deal_value, is_deleted,
                            forecast_category, deal_prediction, deal_prediction_last_updated_at,
                            has_products, rotten_days, last_assigned_at, sales_account_id,
                            last_contacted_sales_activity_mode, last_contacted_via_sales_activity,
                            web_form_id, upcoming_activities_time,
                            cf_pais, cf_integrador, cf_one_time_setup, cf_nro_de_meses,
                            cf_tipo_de_servicio, cf_explique_prdida, cf_valor_total_de_contrato)
                    VALUES (source.id, source.name, source.amount, source.base_currency_amount,
                            source.expected_close, source.closed_date, source.stage_updated_time,
                            source.probability, source.updated_at, source.created_at,
                            source.deal_pipeline_id, source.deal_stage_id, source.age,
                            source.recent_note, source.expected_deal_value, source.is_deleted,
                            source.forecast_category, source.deal_prediction, source.deal_prediction_last_updated_at,
                            source.has_products, source.rotten_days, source.last_assigned_at, source.sales_account_id,
                            source.last_contacted_sales_activity_mode, source.last_contacted_via_sales_activity,
                            source.web_form_id, source.upcoming_activities_time,
                            source.cf_pais, source.cf_integrador, source.cf_one_time_setup,
                            source.cf_nro_de_meses, source.cf_tipo_de_servicio, source.cf_explique_prdida,
                            source.cf_valor_total_de_contrato)
                OUTPUT $action;
            """)

            # Contar resultados
            merge_results = cursor.fetchall()
            for result in merge_results:
                if result[0] == 'INSERT':
                    stats["inserted"] += 1
                elif result[0] == 'UPDATE':
                    stats["updated"] += 1

            # Limpiar tabla temporal
            cursor.execute("DROP TABLE #temp_deals")

            self.connection.commit()
            logger.info(f"Deals loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

            # Extraer y cargar deal_products
            deal_products_stats = self._extract_and_load_deal_products(deals, cursor)
            logger.info(f"Deal products loaded: {deal_products_stats['inserted']} inserted, {deal_products_stats['updated']} updated")

        except Exception as e:
            logger.error(f"Failed to bulk upsert deals: {str(e)}")
            self.connection.rollback()
            stats["failed"] = len(deals)

        finally:
            cursor.close()

        return stats

    def _extract_and_load_deal_products(self, deals: List[Dict], cursor) -> Dict[str, int]:
        """Extrae productos de los deals y los carga en deal_products"""
        stats = {"inserted": 0, "updated": 0, "failed": 0}

        # Recolectar todos los productos de todos los deals
        all_deal_products = []
        for deal in deals:
            deal_id = deal.get("id")
            products = deal.get("products", [])

            for product in products:
                all_deal_products.append({
                    "id": product.get("id"),
                    "deal_id": deal_id,
                    "product_id": product.get("product_id"),
                    "product_name": product.get("name"),
                    "quantity": product.get("quantity"),
                    "unit_price": product.get("unit_price"),
                    "discount": product.get("discount"),
                    "total": product.get("total"),
                    "description": product.get("description")
                })

        if not all_deal_products:
            logger.info("No deal products to load")
            return stats

        logger.info(f"Extracting {len(all_deal_products)} deal products from {len(deals)} deals")

        try:
            # Crear tabla temporal
            cursor.execute("""CREATE TABLE #temp_deal_products (
                freshsale_id BIGINT, deal_id BIGINT, product_id BIGINT, product_name NVARCHAR(500),
                quantity FLOAT, unit_price FLOAT, total_price FLOAT, discount FLOAT, description NVARCHAR(MAX))""")

            # Insertar en tabla temporal
            insert_data = [
                (dp["id"], dp["deal_id"], dp["product_id"], dp.get("product_name"),
                 dp["quantity"], dp["unit_price"], dp["total"], dp["discount"], dp.get("description"))
                for dp in all_deal_products
            ]
            self._bulk_insert(cursor, "#temp_deal_products", [
                "freshsale_id","deal_id","product_id","product_name",
                "quantity","unit_price","total_price","discount","description"
            ], insert_data)

            # DELETE de todos los productos de los deals que estamos procesando
            cursor.execute("""
                DELETE FROM freshsale.deal_products
                WHERE deal_id IN (SELECT DISTINCT deal_id FROM #temp_deal_products)
            """)
            deleted_count = cursor.rowcount

            # INSERT directo desde la tabla temporal
            cursor.execute("""
                INSERT INTO freshsale.deal_products
                (freshsale_id, deal_id, product_id, product_name, quantity, unit_price, total_price, discount, description, etl_created_at, etl_updated_at)
                SELECT freshsale_id, deal_id, product_id, product_name, quantity, unit_price, total_price, discount, description, GETDATE(), GETDATE()
                FROM #temp_deal_products
            """)
            inserted_count = cursor.rowcount

            stats["inserted"] = inserted_count
            logger.info(f"Deleted {deleted_count} existing products, inserted {inserted_count} new products")

            cursor.execute("DROP TABLE #temp_deal_products")
            self.connection.commit()

        except Exception as e:
            logger.error(f"Failed to load deal_products: {str(e)}")
            self.connection.rollback()
            stats["failed"] = len(all_deal_products)

        return stats

    def upsert_users(self, users: List[Dict]) -> Dict[str, int]:
        """Inserta o actualiza usuarios usando BULK INSERT con tabla temporal"""
        stats = {"inserted": 0, "updated": 0, "failed": 0}

        if not users:
            logger.info("No users to load")
            return stats

        cursor = self.connection.cursor()

        try:
            # Crear tabla temporal
            cursor.execute("""
                CREATE TABLE #temp_users (
                    id BIGINT,
                    display_name NVARCHAR(200),
                    email NVARCHAR(255),
                    is_active BIT,
                    work_number NVARCHAR(50),
                    mobile_number NVARCHAR(50)
                )
            """)

            # Preparar datos para bulk insert
            insert_data = []
            for user in users:
                insert_data.append((
                    user["id"],
                    user.get("display_name"),
                    user.get("email"),
                    user.get("is_active", True),
                    user.get("work_number"),
                    user.get("mobile_number")
                ))

            # Bulk insert a tabla temporal
            self._bulk_insert(cursor, "#temp_users", [
                "id","display_name","email","is_active","work_number","mobile_number"
            ], insert_data)

            # MERGE desde tabla temporal a tabla final
            cursor.execute("""
                MERGE freshsale.users AS target
                USING #temp_users AS source ON target.id = source.id
                WHEN MATCHED THEN
                    UPDATE SET
                        display_name = source.display_name,
                        email = source.email,
                        is_active = source.is_active,
                        work_number = source.work_number,
                        mobile_number = source.mobile_number,
                        etl_updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (id, display_name, email, is_active, work_number, mobile_number)
                    VALUES (source.id, source.display_name, source.email, source.is_active,
                            source.work_number, source.mobile_number)
                OUTPUT $action;
            """)

            # Contar resultados
            merge_results = cursor.fetchall()
            for result in merge_results:
                if result[0] == 'INSERT':
                    stats["inserted"] += 1
                elif result[0] == 'UPDATE':
                    stats["updated"] += 1

            # Limpiar tabla temporal
            cursor.execute("DROP TABLE #temp_users")

            self.connection.commit()
            logger.info(f"Users loaded: {stats['inserted']} inserted, {stats['updated']} updated")

        except Exception as e:
            logger.error(f"Failed to bulk upsert users: {str(e)}")
            self.connection.rollback()
            stats["failed"] = len(users)

        finally:
            cursor.close()

        return stats

    def upsert_teams(self, teams: List[Dict]) -> Dict[str, int]:
        """Inserta o actualiza equipos usando BULK INSERT con tabla temporal"""
        stats = {"inserted": 0, "updated": 0, "failed": 0}

        if not teams:
            logger.info("No teams to load")
            return stats

        cursor = self.connection.cursor()

        try:
            # Crear tabla temporal para teams
            cursor.execute("""
                CREATE TABLE #temp_teams (
                    id BIGINT,
                    name NVARCHAR(200)
                )
            """)

            # Preparar datos para bulk insert
            insert_data = []
            for team in teams:
                insert_data.append((
                    team["id"],
                    team.get("name")
                ))

            # Bulk insert a tabla temporal
            self._bulk_insert(cursor, "#temp_teams", ["id","name"], insert_data)

            # MERGE desde tabla temporal a tabla final
            cursor.execute("""
                MERGE freshsale.teams AS target
                USING #temp_teams AS source ON target.id = source.id
                WHEN MATCHED THEN
                    UPDATE SET
                        name = source.name,
                        etl_updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (id, name)
                    VALUES (source.id, source.name)
                OUTPUT $action;
            """)

            # Contar resultados
            merge_results = cursor.fetchall()
            for result in merge_results:
                if result[0] == 'INSERT':
                    stats["inserted"] += 1
                elif result[0] == 'UPDATE':
                    stats["updated"] += 1

            # Limpiar tabla temporal
            cursor.execute("DROP TABLE #temp_teams")

            # Procesar team_users (relaciones)
            for team in teams:
                # Limpiar relaciones anteriores
                cursor.execute("DELETE FROM freshsale.team_users WHERE team_id = %s", (team["id"],))

                # Insertar nuevas relaciones
                user_ids = team.get("user_ids", [])
                if user_ids:
                    team_user_data = [(team["id"], user_id) for user_id in user_ids]
                    self._bulk_insert(cursor, "freshsale.team_users", ["team_id","user_id"], team_user_data)

            self.connection.commit()
            logger.info(f"Teams loaded: {stats['inserted']} inserted, {stats['updated']} updated")

        except Exception as e:
            logger.error(f"Failed to bulk upsert teams: {str(e)}")
            self.connection.rollback()
            stats["failed"] = len(teams)

        finally:
            cursor.close()

        return stats

    @staticmethod
    def _bulk_insert(cursor, table: str, columns: List[str], rows: List[tuple]):
        """
        Inserta múltiples filas en una sola query SQL (un único round-trip).
        Construye: INSERT INTO table (cols) VALUES (r1), (r2), ...
        Divide en batches de 1000 filas para evitar límites de SQL Server.
        """
        if not rows:
            return
        batch_size = 1000
        placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
        col_list = ", ".join(columns)
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            values_clause = ", ".join([placeholders] * len(batch))
            flat_params = [v for row in batch for v in row]
            cursor.execute(
                f"INSERT INTO {table} ({col_list}) VALUES {values_clause}",
                flat_params
            )

    def reset_stats(self):
        """Resetea estadísticas"""
        self.stats = {"inserted": 0, "updated": 0, "failed": 0}
