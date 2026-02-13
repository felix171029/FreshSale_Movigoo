-- ================================================================
-- SCRIPT DE CREACIÓN DE ESQUEMA PARA ETL FRESHSALE -> SQL SERVER
-- ================================================================
-- Este script crea todas las tablas necesarias para almacenar
-- datos de Freshsale en SQL Server
--
-- Modo de ejecución: Verifica si las tablas existen antes de crearlas
-- Si cambia de servidor, solo ejecute este script
-- ================================================================

USE [Movigoo];
GO

-- ================================================================
-- SCHEMA PARA FRESHSALE
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'freshsale')
BEGIN
    EXEC('CREATE SCHEMA freshsale');
    PRINT 'Schema freshsale creado exitosamente';
END
ELSE
BEGIN
    PRINT 'Schema freshsale ya existe';
END
GO

-- ================================================================
-- TABLA DE CONTROL ETL
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.etl_control') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.etl_control (
        id INT IDENTITY(1,1) PRIMARY KEY,
        entity_name NVARCHAR(100) NOT NULL,
        last_execution_date DATETIME NOT NULL,
        execution_status NVARCHAR(50) NOT NULL, -- SUCCESS, ERROR, RUNNING
        records_extracted INT NULL,
        records_inserted INT NULL,
        records_updated INT NULL,
        records_failed INT NULL,
        error_message NVARCHAR(MAX) NULL,
        execution_duration_seconds INT NULL,
        created_at DATETIME DEFAULT GETDATE(),
        CONSTRAINT UQ_entity_last_execution UNIQUE (entity_name, last_execution_date)
    );

    CREATE INDEX IX_etl_control_entity ON freshsale.etl_control(entity_name, last_execution_date DESC);

    PRINT 'Tabla freshsale.etl_control creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.etl_control ya existe';
END
GO

-- ================================================================
-- TABLA DE LOGS
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.etl_log') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.etl_log (
        id INT IDENTITY(1,1) PRIMARY KEY,
        entity_name NVARCHAR(100) NOT NULL,
        log_level NVARCHAR(20) NOT NULL, -- INFO, WARNING, ERROR
        message NVARCHAR(MAX) NOT NULL,
        record_id BIGINT NULL,
        created_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_etl_log_entity_date ON freshsale.etl_log(entity_name, created_at DESC);
    CREATE INDEX IX_etl_log_level ON freshsale.etl_log(log_level, created_at DESC);

    PRINT 'Tabla freshsale.etl_log creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.etl_log ya existe';
END
GO

-- ================================================================
-- TABLA: DEALS (OPORTUNIDADES DE VENTA)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.deals') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.deals (
        id BIGINT PRIMARY KEY,
        name NVARCHAR(500) NOT NULL,
        amount DECIMAL(18,2) NULL,
        base_currency_amount DECIMAL(18,2) NULL,
        expected_close DATE NULL,
        closed_date DATE NULL,
        stage_updated_time DATETIME NULL,
        probability INT NULL,
        updated_at DATETIME NULL,
        created_at DATETIME NULL,
        deal_pipeline_id BIGINT NULL,
        deal_stage_id BIGINT NULL,
        age INT NULL,
        recent_note NVARCHAR(MAX) NULL,
        expected_deal_value DECIMAL(18,2) NULL,
        is_deleted BIT DEFAULT 0,
        forecast_category INT NULL,
        deal_prediction INT NULL,
        deal_prediction_last_updated_at DATETIME NULL,
        has_products BIT DEFAULT 0,
        rotten_days INT NULL,
        last_assigned_at DATETIME NULL,
        last_contacted_sales_activity_mode NVARCHAR(100) NULL,
        last_contacted_via_sales_activity DATETIME NULL,
        web_form_id BIGINT NULL,
        upcoming_activities_time DATETIME NULL,
        -- Custom Fields
        cf_pais NVARCHAR(200) NULL,
        cf_integrador NVARCHAR(MAX) NULL,
        cf_one_time_setup DECIMAL(18,2) NULL,
        cf_nro_de_meses INT NULL,
        cf_tipo_de_servicio NVARCHAR(200) NULL,
        cf_explique_prdida NVARCHAR(MAX) NULL,
        cf_valor_total_de_contrato DECIMAL(18,2) NULL,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_deals_pipeline ON freshsale.deals(deal_pipeline_id);
    CREATE INDEX IX_deals_stage ON freshsale.deals(deal_stage_id);
    CREATE INDEX IX_deals_created ON freshsale.deals(created_at DESC);
    CREATE INDEX IX_deals_updated ON freshsale.deals(updated_at DESC);
    CREATE INDEX IX_deals_closed ON freshsale.deals(closed_date DESC);
    CREATE INDEX IX_deals_deleted ON freshsale.deals(is_deleted);

    PRINT 'Tabla freshsale.deals creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.deals ya existe';
END
GO

-- ================================================================
-- TABLA: DEAL_PRODUCTS (PRODUCTOS ASOCIADOS A DEALS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.deal_products') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.deal_products (
        id INT IDENTITY(1,1) PRIMARY KEY,
        deal_id BIGINT NOT NULL,
        product_id BIGINT NULL,
        product_name NVARCHAR(500) NULL,
        quantity DECIMAL(18,4) NULL,
        unit_price DECIMAL(18,2) NULL,
        total_price DECIMAL(18,2) NULL,
        discount DECIMAL(18,2) NULL,
        description NVARCHAR(MAX) NULL,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE(),
        CONSTRAINT FK_deal_products_deal FOREIGN KEY (deal_id) REFERENCES freshsale.deals(id)
    );

    CREATE INDEX IX_deal_products_deal ON freshsale.deal_products(deal_id);
    CREATE INDEX IX_deal_products_product ON freshsale.deal_products(product_id);

    PRINT 'Tabla freshsale.deal_products creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.deal_products ya existe';
END
GO

-- ================================================================
-- TABLA: CONTACTS (CONTACTOS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.contacts') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.contacts (
        id BIGINT PRIMARY KEY,
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
        created_at DATETIME NULL,
        updated_at DATETIME NULL,
        is_deleted BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_contacts_email ON freshsale.contacts(email);
    CREATE INDEX IX_contacts_owner ON freshsale.contacts(owner_id);
    CREATE INDEX IX_contacts_created ON freshsale.contacts(created_at DESC);
    CREATE INDEX IX_contacts_updated ON freshsale.contacts(updated_at DESC);
    CREATE INDEX IX_contacts_deleted ON freshsale.contacts(is_deleted);

    PRINT 'Tabla freshsale.contacts creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.contacts ya existe';
END
GO

-- ================================================================
-- TABLA: SALES_ACCOUNTS (CUENTAS DE VENTAS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.sales_accounts') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.sales_accounts (
        id BIGINT PRIMARY KEY,
        name NVARCHAR(500) NOT NULL,
        address NVARCHAR(500) NULL,
        city NVARCHAR(100) NULL,
        state NVARCHAR(100) NULL,
        zipcode NVARCHAR(20) NULL,
        country NVARCHAR(100) NULL,
        industry_type_id BIGINT NULL,
        business_type_id BIGINT NULL,
        number_of_employees INT NULL,
        annual_revenue DECIMAL(18,2) NULL,
        website NVARCHAR(500) NULL,
        phone NVARCHAR(50) NULL,
        owner_id BIGINT NULL,
        facebook NVARCHAR(200) NULL,
        twitter NVARCHAR(200) NULL,
        linkedin NVARCHAR(200) NULL,
        territory_id BIGINT NULL,
        created_at DATETIME NULL,
        updated_at DATETIME NULL,
        is_deleted BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_sales_accounts_name ON freshsale.sales_accounts(name);
    CREATE INDEX IX_sales_accounts_owner ON freshsale.sales_accounts(owner_id);
    CREATE INDEX IX_sales_accounts_created ON freshsale.sales_accounts(created_at DESC);
    CREATE INDEX IX_sales_accounts_updated ON freshsale.sales_accounts(updated_at DESC);
    CREATE INDEX IX_sales_accounts_deleted ON freshsale.sales_accounts(is_deleted);

    PRINT 'Tabla freshsale.sales_accounts creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.sales_accounts ya existe';
END
GO

-- ================================================================
-- TABLA: LEADS (PROSPECTOS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.leads') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.leads (
        id BIGINT PRIMARY KEY,
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
        is_deleted BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_leads_email ON freshsale.leads(email);
    CREATE INDEX IX_leads_owner ON freshsale.leads(owner_id);
    CREATE INDEX IX_leads_source ON freshsale.leads(lead_source_id);
    CREATE INDEX IX_leads_stage ON freshsale.leads(lead_stage_id);
    CREATE INDEX IX_leads_created ON freshsale.leads(created_at DESC);
    CREATE INDEX IX_leads_updated ON freshsale.leads(updated_at DESC);
    CREATE INDEX IX_leads_deleted ON freshsale.leads(is_deleted);

    PRINT 'Tabla freshsale.leads creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.leads ya existe';
END
GO

-- ================================================================
-- TABLA: TASKS (TAREAS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.tasks') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.tasks (
        id BIGINT PRIMARY KEY,
        title NVARCHAR(500) NULL,
        description NVARCHAR(MAX) NULL,
        due_date DATETIME NULL,
        status NVARCHAR(50) NULL,
        owner_id BIGINT NULL,
        targetable_type NVARCHAR(100) NULL,
        targetable_id BIGINT NULL,
        created_at DATETIME NULL,
        updated_at DATETIME NULL,
        completed_at DATETIME NULL,
        is_deleted BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_tasks_owner ON freshsale.tasks(owner_id);
    CREATE INDEX IX_tasks_status ON freshsale.tasks(status);
    CREATE INDEX IX_tasks_due_date ON freshsale.tasks(due_date);
    CREATE INDEX IX_tasks_targetable ON freshsale.tasks(targetable_type, targetable_id);
    CREATE INDEX IX_tasks_created ON freshsale.tasks(created_at DESC);
    CREATE INDEX IX_tasks_deleted ON freshsale.tasks(is_deleted);

    PRINT 'Tabla freshsale.tasks creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.tasks ya existe';
END
GO

-- ================================================================
-- TABLA: APPOINTMENTS (CITAS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.appointments') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.appointments (
        id BIGINT PRIMARY KEY,
        title NVARCHAR(500) NULL,
        description NVARCHAR(MAX) NULL,
        from_date DATETIME NULL,
        end_date DATETIME NULL,
        time_zone NVARCHAR(100) NULL,
        location NVARCHAR(500) NULL,
        creater_id BIGINT NULL,
        owner_id BIGINT NULL,
        targetable_type NVARCHAR(100) NULL,
        targetable_id BIGINT NULL,
        created_at DATETIME NULL,
        updated_at DATETIME NULL,
        is_deleted BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_appointments_owner ON freshsale.appointments(owner_id);
    CREATE INDEX IX_appointments_from_date ON freshsale.appointments(from_date);
    CREATE INDEX IX_appointments_targetable ON freshsale.appointments(targetable_type, targetable_id);
    CREATE INDEX IX_appointments_created ON freshsale.appointments(created_at DESC);
    CREATE INDEX IX_appointments_deleted ON freshsale.appointments(is_deleted);

    PRINT 'Tabla freshsale.appointments creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.appointments ya existe';
END
GO

-- ================================================================
-- TABLA: SALES_ACTIVITIES (ACTIVIDADES DE VENTAS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.sales_activities') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.sales_activities (
        id BIGINT PRIMARY KEY,
        title NVARCHAR(500) NULL,
        notes NVARCHAR(MAX) NULL,
        activity_type NVARCHAR(100) NULL,
        start_date DATETIME NULL,
        end_date DATETIME NULL,
        owner_id BIGINT NULL,
        targetable_type NVARCHAR(100) NULL,
        targetable_id BIGINT NULL,
        created_at DATETIME NULL,
        updated_at DATETIME NULL,
        is_deleted BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_sales_activities_owner ON freshsale.sales_activities(owner_id);
    CREATE INDEX IX_sales_activities_type ON freshsale.sales_activities(activity_type);
    CREATE INDEX IX_sales_activities_targetable ON freshsale.sales_activities(targetable_type, targetable_id);
    CREATE INDEX IX_sales_activities_created ON freshsale.sales_activities(created_at DESC);
    CREATE INDEX IX_sales_activities_deleted ON freshsale.sales_activities(is_deleted);

    PRINT 'Tabla freshsale.sales_activities creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.sales_activities ya existe';
END
GO

-- ================================================================
-- TABLA: USERS (USUARIOS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.users') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.users (
        id BIGINT PRIMARY KEY,
        display_name NVARCHAR(500) NULL,
        email NVARCHAR(200) NULL,
        is_active BIT DEFAULT 1,
        work_number NVARCHAR(50) NULL,
        mobile_number NVARCHAR(50) NULL,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_users_email ON freshsale.users(email);
    CREATE INDEX IX_users_active ON freshsale.users(is_active);

    PRINT 'Tabla freshsale.users creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.users ya existe';
END
GO

-- ================================================================
-- TABLA: TEAMS (EQUIPOS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.teams') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.teams (
        id BIGINT PRIMARY KEY,
        name NVARCHAR(500) NOT NULL,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    PRINT 'Tabla freshsale.teams creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.teams ya existe';
END
GO

-- ================================================================
-- TABLA: TEAM_USERS (RELACIÓN EQUIPOS-USUARIOS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.team_users') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.team_users (
        id INT IDENTITY(1,1) PRIMARY KEY,
        team_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        CONSTRAINT UQ_team_user UNIQUE (team_id, user_id),
        CONSTRAINT FK_team_users_team FOREIGN KEY (team_id) REFERENCES freshsale.teams(id),
        CONSTRAINT FK_team_users_user FOREIGN KEY (user_id) REFERENCES freshsale.users(id)
    );

    CREATE INDEX IX_team_users_team ON freshsale.team_users(team_id);
    CREATE INDEX IX_team_users_user ON freshsale.team_users(user_id);

    PRINT 'Tabla freshsale.team_users creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.team_users ya existe';
END
GO

-- ================================================================
-- TABLA: FORECAST_CATEGORIES (CATEGORÍAS DE PRONÓSTICO)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.forecast_categories') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.forecast_categories (
        id BIGINT PRIMARY KEY,
        name NVARCHAR(200) NOT NULL,
        position INT NULL,
        is_default BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_forecast_categories_name ON freshsale.forecast_categories(name);
    CREATE INDEX IX_forecast_categories_position ON freshsale.forecast_categories(position);

    PRINT 'Tabla freshsale.forecast_categories creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.forecast_categories ya existe';
END
GO

-- ================================================================
-- TABLA: DEAL_PREDICTIONS (PREDICCIONES DE DEALS)
-- ================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'freshsale.deal_predictions') AND type = 'U')
BEGIN
    CREATE TABLE freshsale.deal_predictions (
        id BIGINT PRIMARY KEY,
        name NVARCHAR(200) NOT NULL,
        position INT NULL,
        is_default BIT DEFAULT 0,
        -- Metadata ETL
        etl_created_at DATETIME DEFAULT GETDATE(),
        etl_updated_at DATETIME DEFAULT GETDATE()
    );

    CREATE INDEX IX_deal_predictions_name ON freshsale.deal_predictions(name);
    CREATE INDEX IX_deal_predictions_position ON freshsale.deal_predictions(position);

    PRINT 'Tabla freshsale.deal_predictions creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla freshsale.deal_predictions ya existe';
END
GO

PRINT '';
PRINT '================================================================';
PRINT 'SCHEMA CREADO EXITOSAMENTE';
PRINT '================================================================';
PRINT 'Todas las tablas han sido creadas o ya existían.';
PRINT 'Puede ejecutar este script en cualquier servidor SQL sin problemas.';
PRINT '================================================================';
GO
