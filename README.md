
# ETL Freshsale → SQL Server

Sistema completo de ETL (Extract, Transform, Load) para extraer datos de Freshsale CRM y cargarlos en SQL Server con optimizaciones BULK INSERT.

## 📋 Características

- ✅ **Extracción completa** de 13+ entidades de Freshsale
- ✅ **BULK INSERT optimizado** - `executemany()` via pymssql (un solo round-trip)
- ✅ **Auto-creación de tablas** - `ensure_schema_exists()` crea todas las tablas al conectar
- ✅ **Carga incremental** basada en fecha de última actualización
- ✅ **Manejo automático de filtros** para extraer todos los registros (no solo del usuario)
- ✅ **Manejo de errores** con reintentos automáticos y rollback
- ✅ **Control de rate limiting** para evitar bloqueos de API
- ✅ **Logging completo** con auditoría en base de datos
- ✅ **Configuración flexible** mediante variables de entorno (sin credenciales hardcodeadas)

## 📦 Estructura del Proyecto

```
FreshSale_Movigoo/
├── etl/
│   ├── __init__.py
│   ├── freshsale_extractor.py    # Extracción desde Freshsale API
│   ├── sql_loader.py              # Loader base + ensure_schema_exists()
│   └── sql_loader_extended.py     # Loaders para entidades adicionales
├── sql/
│   └── 01_create_schema.sql       # Script SQL de referencia (no requerido)
├── main.py                        # Script principal del ETL
├── config.py                      # Configuración central (lee del .env)
├── .env                           # Credenciales (NO subir a git)
├── .env.example                   # Plantilla de credenciales
├── requirements.txt               # Dependencias de Python
└── README.md                      # Este archivo
```

## 🚀 Instalación

### Requisitos Previos

- **Python 3.8+**
- **SQL Server 2022** (compatible con versiones anteriores)

### Instalación

```bash
# 1. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar credenciales
cp .env.example .env
# Editar .env con las credenciales correctas
```

### Variables de Entorno (`.env`)

```env
FRESHSALE_DOMAIN=tu-empresa.myfreshworks.com
FRESHSALE_API_KEY=tu-api-key

REP_DB_HOST=ip-del-servidor
REP_DB_PORT=1433
REP_DB_NAME=nombre-base-datos
REP_DB_USER=usuario
REP_DB_PASSWORD=contraseña
```

## ▶️ Uso del ETL

### Comandos Principales

```bash
# Carga completa de todas las entidades (primera vez o refresh total)
python3 main.py --full --skip-schema

# Carga incremental (ejecuciones diarias - solo registros modificados)
python3 main.py --skip-schema

# Cargar solo una entidad específica
python3 main.py --entity deals --full --skip-schema
python3 main.py --entity contacts --skip-schema
```

> **Nota:** `--skip-schema` es irrelevante — las tablas se crean automáticamente al conectar. Se mantiene por compatibilidad.

### Entidades Disponibles

| Entidad | Comando | Estado |
|---------|---------|--------|
| Deals + Deal Products | `--entity deals` | ✅ Activo |
| Contacts | `--entity contacts` | ✅ Activo |
| Sales Accounts | `--entity sales_accounts` | ✅ Activo |
| Users | `--entity users` | ✅ Activo |
| Teams | `--entity teams` | ✅ Activo |
| Pipelines | `--entity pipelines` | ✅ Activo |
| Stages | `--entity stages` | ✅ Activo |
| Products | `--entity products` | ✅ Activo |
| Tasks | `--entity tasks` | ✅ Activo |
| Appointments | `--entity appointments` | ✅ Activo |
| Sales Activities | `--entity sales_activities` | ✅ Activo |
| Forecast Categories | `--entity forecast_categories` | ✅ Activo |
| Deal Predictions | `--entity deal_predictions` | ✅ Activo |
| Leads | `--entity leads` | ❌ Deshabilitado (403)* |

\* **Leads deshabilitado**: La API key actual no tiene permisos. Para habilitar, solicitar acceso en Freshsale.

## 🏗️ Arquitectura Técnica

### Driver de Base de Datos

Usa **pymssql** (no pyodbc) por compatibilidad con `NVARCHAR(MAX)` en bulk inserts sobre SQL Server 2022 Linux.

### Patrón BULK INSERT

```
Freshsales API (paginado 100/página)
    → Acumula todos los registros en memoria
    → cursor.executemany() → #temp_entity (un solo round-trip)
    → MERGE #temp_entity → freshsale.entity
    → Commit
```

### Auto-creación de Tablas

Al conectar, `SQLServerLoader.ensure_schema_exists()` verifica y crea automáticamente todas las tablas. No se requieren scripts SQL manuales en un servidor nuevo.

### Tabla `fact_deals_products`

Es una tabla de reporting calculada, **no gestionada por el ETL**. Se actualiza ejecutando el stored procedure en SQL Server:
```sql
EXEC dbo.act_fact_deals_products
```

## 📅 Programación Automática (Cron)

```bash
# Ejecutar diario a las 2 AM
crontab -e

# Agregar:
0 2 * * * cd /ruta/FreshSale_Movigoo && source venv/bin/activate && python3 main.py --skip-schema >> etl_cron.log 2>&1
```

## 📝 Monitoreo

```bash
# Ver log en tiempo real
tail -f etl_freshsale.log
```

```sql
-- Últimas ejecuciones
SELECT TOP 10 * FROM freshsale.etl_control ORDER BY last_execution_date DESC;

-- Ver errores
SELECT * FROM freshsale.etl_control WHERE execution_status = 'ERROR';

-- Conteo por tabla
SELECT 'deals' as entidad, COUNT(*) as total FROM freshsale.deals UNION ALL
SELECT 'contacts', COUNT(*) FROM freshsale.contacts UNION ALL
SELECT 'sales_accounts', COUNT(*) FROM freshsale.sales_accounts;
```

## 🐛 Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `ModuleNotFoundError: dotenv` | venv sin dependencias | `pip install -r requirements.txt` |
| `403 Access Denied` | API key sin permisos | Deshabilitar entidad en `config.py` |
| `zsh: command not found: python` | macOS usa `python3` | Usar `python3` |

## 🔒 Seguridad

- Credenciales exclusivamente en `.env` (no versionado en Git)
- API Token en headers HTTP (no en URL)
- Rollback automático en caso de error

---

**Versión:** 3.0.0
**Última actualización:** Febrero 2026
**Desarrollado para:** Movigoo Innovación SPA
