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
                    cf_nuevo_logo BIT NULL,
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
                    tags NVARCHAR(MAX) NULL,
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
                    created_at DATE NULL,
                    updated_at DATE NULL,
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

                # --- Migraciones: nuevos campos sales_accounts ---
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.sales_accounts') AND name = 'cf_icp_confirmado') ALTER TABLE freshsale.sales_accounts ADD cf_icp_confirmado BIT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.sales_accounts') AND name = 'cf_segmento') ALTER TABLE freshsale.sales_accounts ADD cf_segmento NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.sales_accounts') AND name = 'cf_industria') ALTER TABLE freshsale.sales_accounts ADD cf_industria NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.sales_accounts') AND name = 'cf_tamano_de_empresa') ALTER TABLE freshsale.sales_accounts ADD cf_tamano_de_empresa NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.sales_accounts') AND name = 'cf_propietario_de_la_fuente') ALTER TABLE freshsale.sales_accounts ADD cf_propietario_de_la_fuente NVARCHAR(200) NULL",

                # --- Migraciones: nuevos campos contacts ---
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_contacto_principal') ALTER TABLE freshsale.contacts ADD cf_contacto_principal BIT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_rea_interna') ALTER TABLE freshsale.contacts ADD cf_rea_interna NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_nivel_de_cargo') ALTER TABLE freshsale.contacts ADD cf_nivel_de_cargo NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_pais') ALTER TABLE freshsale.contacts ADD cf_pais NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_servicio_de_inters') ALTER TABLE freshsale.contacts ADD cf_servicio_de_inters NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_lead_creado_por') ALTER TABLE freshsale.contacts ADD cf_lead_creado_por NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_mensaje') ALTER TABLE freshsale.contacts ADD cf_mensaje NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND name = 'cf_rol_del_contacto') ALTER TABLE freshsale.contacts ADD cf_rol_del_contacto NVARCHAR(200) NULL",

                # --- Migraciones: nuevos campos deals ---
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'owner_id') ALTER TABLE freshsale.deals ADD owner_id BIGINT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'deal_type_id') ALTER TABLE freshsale.deals ADD deal_type_id BIGINT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'contact_id') ALTER TABLE freshsale.deals ADD contact_id BIGINT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'lead_source_id') ALTER TABLE freshsale.deals ADD lead_source_id BIGINT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'currency_id') ALTER TABLE freshsale.deals ADD currency_id BIGINT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'deal_reason_id') ALTER TABLE freshsale.deals ADD deal_reason_id BIGINT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'pipeline_name') ALTER TABLE freshsale.deals ADD pipeline_name NVARCHAR(500) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'stage_name') ALTER TABLE freshsale.deals ADD stage_name NVARCHAR(500) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_propietario_de_la_fuente') ALTER TABLE freshsale.deals ADD cf_propietario_de_la_fuente NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_icp_confirmado') ALTER TABLE freshsale.deals ADD cf_icp_confirmado BIT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_problema__necesidad') ALTER TABLE freshsale.deals ADD cf_problema__necesidad NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_caso_de_uso') ALTER TABLE freshsale.deals ADD cf_caso_de_uso NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_riesgos_finales') ALTER TABLE freshsale.deals ADD cf_riesgos_finales NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_feedback_cliente') ALTER TABLE freshsale.deals ADD cf_feedback_cliente NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_acv') ALTER TABLE freshsale.deals ADD cf_acv DECIMAL(18,2) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_alcance__servicios_incluidos') ALTER TABLE freshsale.deals ADD cf_alcance__servicios_incluidos NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_prximo_paso') ALTER TABLE freshsale.deals ADD cf_prximo_paso NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_del_prximo_paso') ALTER TABLE freshsale.deals ADD cf_fecha_del_prximo_paso DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_envo_propuesta') ALTER TABLE freshsale.deals ADD cf_fecha_envo_propuesta DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_objetivo_de_la_demo') ALTER TABLE freshsale.deals ADD cf_objetivo_de_la_demo NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_tipo_de_demo') ALTER TABLE freshsale.deals ADD cf_tipo_de_demo NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_demo_agendada') ALTER TABLE freshsale.deals ADD cf_fecha_demo_agendada DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_demo_realizada') ALTER TABLE freshsale.deals ADD cf_fecha_demo_realizada DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_resultado_de_demo') ALTER TABLE freshsale.deals ADD cf_resultado_de_demo NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fit_solucin__caso_de_uso') ALTER TABLE freshsale.deals ADD cf_fit_solucin__caso_de_uso NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_estado_de_renovacin') ALTER TABLE freshsale.deals ADD cf_estado_de_renovacin NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_fin_contrato') ALTER TABLE freshsale.deals ADD cf_fecha_fin_contrato DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_riesgo_rav') ALTER TABLE freshsale.deals ADD cf_riesgo_rav NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_motivo_de_riesgo') ALTER TABLE freshsale.deals ADD cf_motivo_de_riesgo NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_ltimo_contacto_cliente') ALTER TABLE freshsale.deals ADD cf_ltimo_contacto_cliente DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_estado_de_usoadopcin') ALTER TABLE freshsale.deals ADD cf_estado_de_usoadopcin NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_trminos_comerciales') ALTER TABLE freshsale.deals ADD cf_trminos_comerciales NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_ajuste_de_precio_si_aplica') ALTER TABLE freshsale.deals ADD cf_ajuste_de_precio_si_aplica NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_de_firma_prevista') ALTER TABLE freshsale.deals ADD cf_fecha_de_firma_prevista DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_tipo_de_expansin') ALTER TABLE freshsale.deals ADD cf_tipo_de_expansin NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_impacto_esperado') ALTER TABLE freshsale.deals ADD cf_impacto_esperado NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_estado_legal__procurementno_aplica') ALTER TABLE freshsale.deals ADD cf_estado_legal__procurementno_aplica NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_solicitud_de_contrato') ALTER TABLE freshsale.deals ADD cf_fecha_solicitud_de_contrato DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_contrato_enviado') ALTER TABLE freshsale.deals ADD cf_contrato_enviado BIT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_contrato_enviado') ALTER TABLE freshsale.deals ADD cf_fecha_contrato_enviado DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_contrato_firmado') ALTER TABLE freshsale.deals ADD cf_contrato_firmado BIT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_contrato_firmado') ALTER TABLE freshsale.deals ADD cf_fecha_contrato_firmado DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_owner_administrativo__legal') ALTER TABLE freshsale.deals ADD cf_owner_administrativo__legal NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_link_de_contraro') ALTER TABLE freshsale.deals ADD cf_link_de_contraro NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_tipo_de_contrato') ALTER TABLE freshsale.deals ADD cf_tipo_de_contrato NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_versin__redlines_requeridos') ALTER TABLE freshsale.deals ADD cf_versin__redlines_requeridos NVARCHAR(200) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_bloqueador_actual_de_contrato') ALTER TABLE freshsale.deals ADD cf_bloqueador_actual_de_contrato NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_compromiso_de_firma') ALTER TABLE freshsale.deals ADD cf_fecha_compromiso_de_firma DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_requiere_po__orden_de_compra') ALTER TABLE freshsale.deals ADD cf_requiere_po__orden_de_compra BIT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_po_recibida') ALTER TABLE freshsale.deals ADD cf_po_recibida BIT NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_fecha_recepcin_po') ALTER TABLE freshsale.deals ADD cf_fecha_recepcin_po DATE NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_motivo_de_atraso_contractual') ALTER TABLE freshsale.deals ADD cf_motivo_de_atraso_contractual NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_comentarios_jurdicos__administrativos') ALTER TABLE freshsale.deals ADD cf_comentarios_jurdicos__administrativos NVARCHAR(MAX) NULL",
                "IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'freshsale.deals') AND name = 'cf_nuevo_logo') ALTER TABLE freshsale.deals ADD cf_nuevo_logo BIT NULL",
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

    def upsert_deals(self, deals: List[Dict], pipeline_map: Dict = None, stage_map: Dict = None) -> Dict[str, int]:
        """Inserta o actualiza deals usando BULK INSERT con tabla temporal"""
        stats = {"inserted": 0, "updated": 0, "failed": 0}

        if not deals:
            logger.info("No deals to load")
            return stats

        if pipeline_map is None:
            pipeline_map = {}
        if stage_map is None:
            stage_map = {}

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
                    pipeline_name NVARCHAR(500),
                    stage_name NVARCHAR(500),
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
                    owner_id BIGINT,
                    deal_type_id BIGINT,
                    contact_id BIGINT,
                    sales_account_id BIGINT,
                    lead_source_id BIGINT,
                    currency_id BIGINT,
                    deal_reason_id BIGINT,
                    last_contacted_sales_activity_mode NVARCHAR(100),
                    last_contacted_via_sales_activity DATETIME2,
                    web_form_id BIGINT,
                    upcoming_activities_time DATETIME2,
                    cf_pais NVARCHAR(200),
                    cf_propietario_de_la_fuente NVARCHAR(200),
                    cf_icp_confirmado BIT,
                    cf_problema__necesidad NVARCHAR(MAX),
                    cf_caso_de_uso NVARCHAR(200),
                    cf_riesgos_finales NVARCHAR(MAX),
                    cf_feedback_cliente NVARCHAR(MAX),
                    cf_nro_de_meses BIGINT,
                    cf_tipo_de_servicio NVARCHAR(200),
                    cf_one_time_setup FLOAT,
                    cf_valor_total_de_contrato FLOAT,
                    cf_acv DECIMAL(18,2),
                    cf_alcance__servicios_incluidos NVARCHAR(MAX),
                    cf_prximo_paso NVARCHAR(MAX),
                    cf_fecha_del_prximo_paso DATE,
                    cf_fecha_envo_propuesta DATE,
                    cf_objetivo_de_la_demo NVARCHAR(MAX),
                    cf_tipo_de_demo NVARCHAR(200),
                    cf_fecha_demo_agendada DATE,
                    cf_fecha_demo_realizada DATE,
                    cf_resultado_de_demo NVARCHAR(MAX),
                    cf_fit_solucin__caso_de_uso NVARCHAR(MAX),
                    cf_estado_de_renovacin NVARCHAR(200),
                    cf_fecha_fin_contrato DATE,
                    cf_riesgo_rav NVARCHAR(200),
                    cf_motivo_de_riesgo NVARCHAR(MAX),
                    cf_ltimo_contacto_cliente DATE,
                    cf_estado_de_usoadopcin NVARCHAR(200),
                    cf_trminos_comerciales NVARCHAR(MAX),
                    cf_ajuste_de_precio_si_aplica NVARCHAR(MAX),
                    cf_fecha_de_firma_prevista DATE,
                    cf_tipo_de_expansin NVARCHAR(200),
                    cf_impacto_esperado NVARCHAR(MAX),
                    cf_estado_legal__procurementno_aplica NVARCHAR(200),
                    cf_fecha_solicitud_de_contrato DATE,
                    cf_contrato_enviado BIT,
                    cf_fecha_contrato_enviado DATE,
                    cf_contrato_firmado BIT,
                    cf_fecha_contrato_firmado DATE,
                    cf_owner_administrativo__legal NVARCHAR(200),
                    cf_link_de_contraro NVARCHAR(MAX),
                    cf_tipo_de_contrato NVARCHAR(200),
                    cf_versin__redlines_requeridos NVARCHAR(200),
                    cf_bloqueador_actual_de_contrato NVARCHAR(MAX),
                    cf_fecha_compromiso_de_firma DATE,
                    cf_requiere_po__orden_de_compra BIT,
                    cf_po_recibida BIT,
                    cf_fecha_recepcin_po DATE,
                    cf_motivo_de_atraso_contractual NVARCHAR(MAX),
                    cf_comentarios_jurdicos__administrativos NVARCHAR(MAX),
                    cf_explique_prdida NVARCHAR(MAX),
                    cf_integrador NVARCHAR(4000),
                    cf_nuevo_logo BIT
                )
            """)

            # Preparar datos para bulk insert (mismo orden que tabla temporal)
            insert_data = []
            for deal in deals:
                cf = deal.get("custom_field", {})

                # Conversión BIT para cf_icp_confirmado
                icp_val = cf.get("cf_icp_confirmado")
                icp_bit = True if str(icp_val).lower() in ("true", "1", "si", "sí", "yes") else (False if icp_val is not None else None)

                # Conversión BIT para checkboxes contractuales
                def to_bit(val):
                    if val is None:
                        return None
                    return True if str(val).lower() in ("true", "1", "si", "sí", "yes") else False

                # Primer contacto del deal (contacts es lista)
                contacts_list = deal.get("contacts", [])
                contact_id = contacts_list[0].get("id") if contacts_list else None

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
                    pipeline_map.get(deal.get("deal_pipeline_id")),
                    stage_map.get(deal.get("deal_stage_id")),
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
                    deal.get("owner_id"),
                    deal.get("deal_type_id"),
                    contact_id,
                    deal.get("sales_account_id"),
                    deal.get("lead_source_id"),
                    deal.get("currency_id"),
                    deal.get("deal_reason_id"),
                    deal.get("last_contacted_sales_activity_mode"),
                    self.parse_date(deal.get("last_contacted_via_sales_activity")),
                    deal.get("web_form_id"),
                    self.parse_date(deal.get("upcoming_activities_time")),
                    cf.get("cf_pais"),
                    cf.get("cf_propietario_de_la_fuente"),
                    icp_bit,
                    cf.get("cf_problema__necesidad"),
                    cf.get("cf_caso_de_uso"),
                    cf.get("cf_riesgos_finales"),
                    cf.get("cf_feedback_cliente"),
                    cf.get("cf_nro_de_meses"),
                    cf.get("cf_tipo_de_servicio"),
                    cf.get("cf_one_time_setup"),
                    cf.get("cf_valor_total_de_contrato"),
                    cf.get("cf_acv"),
                    cf.get("cf_alcance__servicios_incluidos"),
                    cf.get("cf_prximo_paso"),
                    self.parse_date(cf.get("cf_fecha_del_prximo_paso")),
                    self.parse_date(cf.get("cf_fecha_envo_propuesta")),
                    cf.get("cf_objetivo_de_la_demo"),
                    cf.get("cf_tipo_de_demo"),
                    self.parse_date(cf.get("cf_fecha_demo_agendada")),
                    self.parse_date(cf.get("cf_fecha_demo_realizada")),
                    cf.get("cf_resultado_de_demo"),
                    cf.get("cf_fit_solucin__caso_de_uso"),
                    cf.get("cf_estado_de_renovacin"),
                    self.parse_date(cf.get("cf_fecha_fin_contrato")),
                    cf.get("cf_riesgo_rav"),
                    cf.get("cf_motivo_de_riesgo"),
                    self.parse_date(cf.get("cf_ltimo_contacto_cliente")),
                    cf.get("cf_estado_de_usoadopcin"),
                    cf.get("cf_trminos_comerciales"),
                    cf.get("cf_ajuste_de_precio_si_aplica"),
                    self.parse_date(cf.get("cf_fecha_de_firma_prevista")),
                    cf.get("cf_tipo_de_expansin"),
                    cf.get("cf_impacto_esperado"),
                    cf.get("cf_estado_legal__procurementno_aplica"),
                    self.parse_date(cf.get("cf_fecha_solicitud_de_contrato")),
                    to_bit(cf.get("cf_contrato_enviado")),
                    self.parse_date(cf.get("cf_fecha_contrato_enviado")),
                    to_bit(cf.get("cf_contrato_firmado")),
                    self.parse_date(cf.get("cf_fecha_contrato_firmado")),
                    cf.get("cf_owner_administrativo__legal"),
                    cf.get("cf_link_de_contraro"),
                    cf.get("cf_tipo_de_contrato"),
                    cf.get("cf_versin__redlines_requeridos"),
                    cf.get("cf_bloqueador_actual_de_contrato"),
                    self.parse_date(cf.get("cf_fecha_compromiso_de_firma")),
                    to_bit(cf.get("cf_requiere_po__orden_de_compra")),
                    to_bit(cf.get("cf_po_recibida")),
                    self.parse_date(cf.get("cf_fecha_recepcin_po")),
                    cf.get("cf_motivo_de_atraso_contractual"),
                    cf.get("cf_comentarios_jurdicos__administrativos"),
                    cf.get("cf_explique_prdida"),
                    cf.get("cf_integrador"),
                    to_bit(cf.get("cf_nuevo_logo")),
                ))

            # Bulk insert: single multi-row INSERT (un solo round-trip)
            self._bulk_insert(cursor, "#temp_deals", [
                "id","name","amount","base_currency_amount","expected_close","closed_date",
                "stage_updated_time","probability","updated_at","created_at","deal_pipeline_id",
                "deal_stage_id","pipeline_name","stage_name","age","recent_note","expected_deal_value",
                "is_deleted","forecast_category","deal_prediction","deal_prediction_last_updated_at",
                "has_products","rotten_days","last_assigned_at","owner_id","deal_type_id","contact_id",
                "sales_account_id","lead_source_id","currency_id","deal_reason_id",
                "last_contacted_sales_activity_mode","last_contacted_via_sales_activity",
                "web_form_id","upcoming_activities_time",
                "cf_pais","cf_propietario_de_la_fuente","cf_icp_confirmado","cf_problema__necesidad",
                "cf_caso_de_uso","cf_riesgos_finales","cf_feedback_cliente","cf_nro_de_meses",
                "cf_tipo_de_servicio","cf_one_time_setup","cf_valor_total_de_contrato","cf_acv",
                "cf_alcance__servicios_incluidos","cf_prximo_paso","cf_fecha_del_prximo_paso",
                "cf_fecha_envo_propuesta","cf_objetivo_de_la_demo","cf_tipo_de_demo",
                "cf_fecha_demo_agendada","cf_fecha_demo_realizada","cf_resultado_de_demo",
                "cf_fit_solucin__caso_de_uso","cf_estado_de_renovacin","cf_fecha_fin_contrato",
                "cf_riesgo_rav","cf_motivo_de_riesgo","cf_ltimo_contacto_cliente",
                "cf_estado_de_usoadopcin","cf_trminos_comerciales","cf_ajuste_de_precio_si_aplica",
                "cf_fecha_de_firma_prevista","cf_tipo_de_expansin","cf_impacto_esperado",
                "cf_estado_legal__procurementno_aplica","cf_fecha_solicitud_de_contrato",
                "cf_contrato_enviado","cf_fecha_contrato_enviado","cf_contrato_firmado",
                "cf_fecha_contrato_firmado","cf_owner_administrativo__legal","cf_link_de_contraro",
                "cf_tipo_de_contrato","cf_versin__redlines_requeridos","cf_bloqueador_actual_de_contrato",
                "cf_fecha_compromiso_de_firma","cf_requiere_po__orden_de_compra","cf_po_recibida",
                "cf_fecha_recepcin_po","cf_motivo_de_atraso_contractual",
                "cf_comentarios_jurdicos__administrativos","cf_explique_prdida","cf_integrador",
                "cf_nuevo_logo"
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
                        pipeline_name = source.pipeline_name,
                        stage_name = source.stage_name,
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
                        owner_id = source.owner_id,
                        deal_type_id = source.deal_type_id,
                        contact_id = source.contact_id,
                        sales_account_id = source.sales_account_id,
                        lead_source_id = source.lead_source_id,
                        currency_id = source.currency_id,
                        deal_reason_id = source.deal_reason_id,
                        last_contacted_sales_activity_mode = source.last_contacted_sales_activity_mode,
                        last_contacted_via_sales_activity = source.last_contacted_via_sales_activity,
                        web_form_id = source.web_form_id,
                        upcoming_activities_time = source.upcoming_activities_time,
                        cf_pais = source.cf_pais,
                        cf_propietario_de_la_fuente = source.cf_propietario_de_la_fuente,
                        cf_icp_confirmado = source.cf_icp_confirmado,
                        cf_problema__necesidad = source.cf_problema__necesidad,
                        cf_caso_de_uso = source.cf_caso_de_uso,
                        cf_riesgos_finales = source.cf_riesgos_finales,
                        cf_feedback_cliente = source.cf_feedback_cliente,
                        cf_nro_de_meses = source.cf_nro_de_meses,
                        cf_tipo_de_servicio = source.cf_tipo_de_servicio,
                        cf_one_time_setup = source.cf_one_time_setup,
                        cf_valor_total_de_contrato = source.cf_valor_total_de_contrato,
                        cf_acv = source.cf_acv,
                        cf_alcance__servicios_incluidos = source.cf_alcance__servicios_incluidos,
                        cf_prximo_paso = source.cf_prximo_paso,
                        cf_fecha_del_prximo_paso = source.cf_fecha_del_prximo_paso,
                        cf_fecha_envo_propuesta = source.cf_fecha_envo_propuesta,
                        cf_objetivo_de_la_demo = source.cf_objetivo_de_la_demo,
                        cf_tipo_de_demo = source.cf_tipo_de_demo,
                        cf_fecha_demo_agendada = source.cf_fecha_demo_agendada,
                        cf_fecha_demo_realizada = source.cf_fecha_demo_realizada,
                        cf_resultado_de_demo = source.cf_resultado_de_demo,
                        cf_fit_solucin__caso_de_uso = source.cf_fit_solucin__caso_de_uso,
                        cf_estado_de_renovacin = source.cf_estado_de_renovacin,
                        cf_fecha_fin_contrato = source.cf_fecha_fin_contrato,
                        cf_riesgo_rav = source.cf_riesgo_rav,
                        cf_motivo_de_riesgo = source.cf_motivo_de_riesgo,
                        cf_ltimo_contacto_cliente = source.cf_ltimo_contacto_cliente,
                        cf_estado_de_usoadopcin = source.cf_estado_de_usoadopcin,
                        cf_trminos_comerciales = source.cf_trminos_comerciales,
                        cf_ajuste_de_precio_si_aplica = source.cf_ajuste_de_precio_si_aplica,
                        cf_fecha_de_firma_prevista = source.cf_fecha_de_firma_prevista,
                        cf_tipo_de_expansin = source.cf_tipo_de_expansin,
                        cf_impacto_esperado = source.cf_impacto_esperado,
                        cf_estado_legal__procurementno_aplica = source.cf_estado_legal__procurementno_aplica,
                        cf_fecha_solicitud_de_contrato = source.cf_fecha_solicitud_de_contrato,
                        cf_contrato_enviado = source.cf_contrato_enviado,
                        cf_fecha_contrato_enviado = source.cf_fecha_contrato_enviado,
                        cf_contrato_firmado = source.cf_contrato_firmado,
                        cf_fecha_contrato_firmado = source.cf_fecha_contrato_firmado,
                        cf_owner_administrativo__legal = source.cf_owner_administrativo__legal,
                        cf_link_de_contraro = source.cf_link_de_contraro,
                        cf_tipo_de_contrato = source.cf_tipo_de_contrato,
                        cf_versin__redlines_requeridos = source.cf_versin__redlines_requeridos,
                        cf_bloqueador_actual_de_contrato = source.cf_bloqueador_actual_de_contrato,
                        cf_fecha_compromiso_de_firma = source.cf_fecha_compromiso_de_firma,
                        cf_requiere_po__orden_de_compra = source.cf_requiere_po__orden_de_compra,
                        cf_po_recibida = source.cf_po_recibida,
                        cf_fecha_recepcin_po = source.cf_fecha_recepcin_po,
                        cf_motivo_de_atraso_contractual = source.cf_motivo_de_atraso_contractual,
                        cf_comentarios_jurdicos__administrativos = source.cf_comentarios_jurdicos__administrativos,
                        cf_explique_prdida = source.cf_explique_prdida,
                        cf_integrador = source.cf_integrador,
                        cf_nuevo_logo = source.cf_nuevo_logo,
                        etl_updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (id, name, amount, base_currency_amount, expected_close,
                            closed_date, stage_updated_time, probability, updated_at,
                            created_at, deal_pipeline_id, deal_stage_id, pipeline_name, stage_name,
                            age, recent_note, expected_deal_value, is_deleted,
                            forecast_category, deal_prediction, deal_prediction_last_updated_at,
                            has_products, rotten_days, last_assigned_at,
                            owner_id, deal_type_id, contact_id, sales_account_id,
                            lead_source_id, currency_id, deal_reason_id,
                            last_contacted_sales_activity_mode, last_contacted_via_sales_activity,
                            web_form_id, upcoming_activities_time,
                            cf_pais, cf_propietario_de_la_fuente, cf_icp_confirmado,
                            cf_problema__necesidad, cf_caso_de_uso, cf_riesgos_finales, cf_feedback_cliente,
                            cf_nro_de_meses, cf_tipo_de_servicio, cf_one_time_setup, cf_valor_total_de_contrato,
                            cf_acv, cf_alcance__servicios_incluidos, cf_prximo_paso,
                            cf_fecha_del_prximo_paso, cf_fecha_envo_propuesta,
                            cf_objetivo_de_la_demo, cf_tipo_de_demo, cf_fecha_demo_agendada,
                            cf_fecha_demo_realizada, cf_resultado_de_demo, cf_fit_solucin__caso_de_uso,
                            cf_estado_de_renovacin, cf_fecha_fin_contrato, cf_riesgo_rav,
                            cf_motivo_de_riesgo, cf_ltimo_contacto_cliente, cf_estado_de_usoadopcin,
                            cf_trminos_comerciales, cf_ajuste_de_precio_si_aplica, cf_fecha_de_firma_prevista,
                            cf_tipo_de_expansin, cf_impacto_esperado, cf_estado_legal__procurementno_aplica,
                            cf_fecha_solicitud_de_contrato, cf_contrato_enviado, cf_fecha_contrato_enviado,
                            cf_contrato_firmado, cf_fecha_contrato_firmado, cf_owner_administrativo__legal,
                            cf_link_de_contraro, cf_tipo_de_contrato, cf_versin__redlines_requeridos,
                            cf_bloqueador_actual_de_contrato, cf_fecha_compromiso_de_firma,
                            cf_requiere_po__orden_de_compra, cf_po_recibida, cf_fecha_recepcin_po,
                            cf_motivo_de_atraso_contractual, cf_comentarios_jurdicos__administrativos,
                            cf_explique_prdida, cf_integrador, cf_nuevo_logo)
                    VALUES (source.id, source.name, source.amount, source.base_currency_amount,
                            source.expected_close, source.closed_date, source.stage_updated_time,
                            source.probability, source.updated_at, source.created_at,
                            source.deal_pipeline_id, source.deal_stage_id, source.pipeline_name, source.stage_name,
                            source.age, source.recent_note, source.expected_deal_value, source.is_deleted,
                            source.forecast_category, source.deal_prediction, source.deal_prediction_last_updated_at,
                            source.has_products, source.rotten_days, source.last_assigned_at,
                            source.owner_id, source.deal_type_id, source.contact_id, source.sales_account_id,
                            source.lead_source_id, source.currency_id, source.deal_reason_id,
                            source.last_contacted_sales_activity_mode, source.last_contacted_via_sales_activity,
                            source.web_form_id, source.upcoming_activities_time,
                            source.cf_pais, source.cf_propietario_de_la_fuente, source.cf_icp_confirmado,
                            source.cf_problema__necesidad, source.cf_caso_de_uso, source.cf_riesgos_finales,
                            source.cf_feedback_cliente, source.cf_nro_de_meses, source.cf_tipo_de_servicio,
                            source.cf_one_time_setup, source.cf_valor_total_de_contrato, source.cf_acv,
                            source.cf_alcance__servicios_incluidos, source.cf_prximo_paso,
                            source.cf_fecha_del_prximo_paso, source.cf_fecha_envo_propuesta,
                            source.cf_objetivo_de_la_demo, source.cf_tipo_de_demo, source.cf_fecha_demo_agendada,
                            source.cf_fecha_demo_realizada, source.cf_resultado_de_demo,
                            source.cf_fit_solucin__caso_de_uso, source.cf_estado_de_renovacin,
                            source.cf_fecha_fin_contrato, source.cf_riesgo_rav, source.cf_motivo_de_riesgo,
                            source.cf_ltimo_contacto_cliente, source.cf_estado_de_usoadopcin,
                            source.cf_trminos_comerciales, source.cf_ajuste_de_precio_si_aplica,
                            source.cf_fecha_de_firma_prevista, source.cf_tipo_de_expansin,
                            source.cf_impacto_esperado, source.cf_estado_legal__procurementno_aplica,
                            source.cf_fecha_solicitud_de_contrato, source.cf_contrato_enviado,
                            source.cf_fecha_contrato_enviado, source.cf_contrato_firmado,
                            source.cf_fecha_contrato_firmado, source.cf_owner_administrativo__legal,
                            source.cf_link_de_contraro, source.cf_tipo_de_contrato,
                            source.cf_versin__redlines_requeridos, source.cf_bloqueador_actual_de_contrato,
                            source.cf_fecha_compromiso_de_firma, source.cf_requiere_po__orden_de_compra,
                            source.cf_po_recibida, source.cf_fecha_recepcin_po,
                            source.cf_motivo_de_atraso_contractual, source.cf_comentarios_jurdicos__administrativos,
                            source.cf_explique_prdida, source.cf_integrador, source.cf_nuevo_logo)
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
