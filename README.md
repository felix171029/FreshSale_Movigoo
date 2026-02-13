
# ETL Freshsale → SQL Server

Sistema completo de ETL (Extract, Transform, Load) para extraer datos de Freshsale CRM y cargarlos en SQL Server con optimizaciones BULK INSERT.

## 📋 Características

- ✅ **Extracción completa** de 11 entidades de Freshsale
- ✅ **BULK INSERT optimizado** - Carga masiva usando tablas temporales y MERGE
- ✅ **Carga incremental** basada en fecha de última actualización
- ✅ **Manejo automático de filtros** para extraer todos los registros (no solo del usuario)
- ✅ **Manejo de errores** con reintentos automáticos y rollback
- ✅ **Control de rate limiting** para evitar bloqueos de API
- ✅ **Logging completo** con auditoría en base de datos
- ✅ **Scripts SQL idempotentes** - se pueden ejecutar múltiples veces
- ✅ **Configuración flexible** mediante variables de entorno

## 📦 Estructura del Proyecto

```
FreshSale - Movigoo/
├── etl/
│   ├── __init__.py
│   ├── freshsale_extractor.py    # Extracción desde Freshsale API
│   ├── sql_loader.py              # Loaders base (deals, users, teams)
│   └── sql_loader_extended.py     # Loaders extendidos (otras entidades)
├── sql/
│   └── 01_create_schema.sql       # Script de creación de tablas
├── main.py                        # Script principal del ETL
├── config.py                      # Configuración central
├── .env                           # Credenciales (NO subir a git)
├── .env.example                   # Plantilla de credenciales
├── requirements.txt               # Dependencias de Python
└── README.md                      # Este archivo
```

## 🚀 Instalación Rápida

### Requisitos Previos

- **Python 3.8+**
- **ODBC Driver 18 for SQL Server**

### Instalación

```bash
# 1. Clonar/descargar el proyecto
cd "/Users/felix/FreshSale - Movigoo"

# 2. Crear entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar credenciales (ya configurado)
# Editar .env si es necesario
```

## ▶️ Uso del ETL

### Comandos Principales

```bash
# Carga completa de todas las entidades (primera vez)
python main.py --full --skip-schema

# Carga incremental (ejecuciones diarias)
python main.py --skip-schema

# Cargar solo una entidad específica
python main.py --entity deals --skip-schema
python main.py --entity contacts --skip-schema
python main.py --entity sales_accounts --skip-schema
```

### Entidades Disponibles

| Entidad | Comando | Registros | Tiempo Aprox | Estado |
|---------|---------|-----------|--------------|--------|
| **Deals** | `--entity deals` | 405 | ~1.7 min | ✅ Activo |
| **Contacts** | `--entity contacts` | 16,930 | ~12.6 min | ✅ Activo |
| **Sales Accounts** | `--entity sales_accounts` | 2,210 | ~1 min | ✅ Activo |
| **Users** | `--entity users` | 11 | <5 seg | ✅ Activo |
| **Teams** | `--entity teams` | 2 | <5 seg | ✅ Activo |
| **Pipelines** | `--entity pipelines` | 5 | <5 seg | ✅ Activo |
| **Stages** | `--entity stages` | 30 | <10 seg | ✅ Activo |
| **Products** | `--entity products` | 25 | <5 seg | ✅ Activo |
| **Tasks** | `--entity tasks` | 0 | - | ⚪ Sin datos |
| **Appointments** | `--entity appointments` | 0 | - | ⚪ Sin datos |
| **Sales Activities** | `--entity sales_activities` | 0 | - | ⚪ Sin datos |
| **Leads** | `--entity leads` | - | - | ❌ Deshabilitado* |

\* **Leads deshabilitado**: La API key actual no tiene permisos de acceso (403 Access Denied). Para habilitarlo, contactar soporte de Freshsale.

### Opciones Disponibles

```bash
--full           # Carga completa (ignorar última ejecución)
--entity NOMBRE  # Procesar solo una entidad específica
--skip-schema    # Saltar creación de tablas (recomendado si ya existen)
```

## 📊 Resultados de Última Ejecución

**Fecha:** 06 Febrero 2026
**Duración total:** 15 minutos 55 segundos
**Registros procesados:** 19,618
**Registros cargados exitosamente:** 19,593
**Registros fallidos:** 25 (products - ya corregido)

### Desglose por Entidad

- ✅ Deals: 405 actualizados
- ✅ Contacts: 16,930 actualizados
- ✅ Sales Accounts: 2,210 actualizados
- ✅ Users: 11 actualizados
- ✅ Teams: 2 actualizados
- ✅ Pipelines: 5 actualizados
- ✅ Stages: 30 actualizados
- ⚪ Tasks: 0 (sin datos en CRM)
- ⚪ Appointments: 0 (sin datos en CRM)
- ⚪ Sales Activities: 0 (sin datos en CRM)
- ✅ Products: 25 (corregido)

## 🔧 Configuración

### Filtros Configurados

El ETL está configurado para extraer **TODOS** los registros (no solo del propietario del API key):

- **Deals**: Filter ID 28001560042 ("All Deals")
- **Contacts**: Filter ID 28001560030 ("All Contacts")
- **Sales Accounts**: Filter ID 28001560057 ("All Accounts")
- **Leads**: Filter ID 28001560017 ("All Leads") - Deshabilitado por permisos

### Carga Incremental

Las entidades con `incremental: True` solo extraen registros modificados desde la última ejecución exitosa:

- Deals, Contacts, Sales Accounts, Products: **Incremental**
- Users, Teams, Pipelines, Stages: **Carga completa siempre**

## 🏗️ Arquitectura Técnica

### Optimización BULK INSERT

Todas las funciones de carga utilizan el patrón optimizado:

1. **Crear tabla temporal** (#temp_entity)
2. **Insertar datos** individualmente a tabla temporal (evita buffer overflow)
3. **MERGE** masivo de tabla temporal → tabla final
4. **Contar** INSERTs y UPDATEs mediante OUTPUT $action
5. **Cleanup** y commit

**Ventaja:** Reduce ~4,420 queries individuales a 3 operaciones para 2,210 registros (~99.9% reducción).

### Manejo de Errores

- **Rollback automático** en caso de error durante MERGE
- **Reintentos** con backoff exponencial para API calls
- **Logging detallado** en archivo y consola
- **Estadísticas** de inserted/updated/failed por entidad

## 📅 Programación Automática

### Linux/Mac (Cron)

```bash
# Ejecutar diario a las 2 AM
crontab -e

# Agregar:
0 2 * * * cd /Users/felix/FreshSale\ -\ Movigoo && source venv/bin/activate && python main.py --skip-schema >> etl_cron.log 2>&1
```

### Windows (Task Scheduler)

1. Abrir Task Scheduler
2. Crear tarea básica
3. Trigger: Diario a las 02:00
4. Action: Ejecutar programa
   - Programa: `C:\Python\python.exe`
   - Argumentos: `main.py --skip-schema`
   - Directorio: `C:\ruta\FreshSale - Movigoo`

## 📝 Logs y Monitoreo

### Archivo de Log

```bash
# Ver log en tiempo real
tail -f etl_freshsale.log

# Windows PowerShell
Get-Content etl_freshsale.log -Wait
```

### Consultas SQL Útiles

```sql
-- Ver últimas ejecuciones
SELECT TOP 10 *
FROM freshsale.etl_control
ORDER BY last_execution_date DESC;

-- Ver errores
SELECT *
FROM freshsale.etl_control
WHERE execution_status = 'ERROR';

-- Contar registros por entidad
SELECT 'deals' as entity, COUNT(*) as total FROM freshsale.deals UNION ALL
SELECT 'contacts', COUNT(*) FROM freshsale.contacts UNION ALL
SELECT 'sales_accounts', COUNT(*) FROM freshsale.sales_accounts;
```

## 🐛 Solución de Problemas Comunes

### Error: "Communication link failure"

**Causa:** Timeout de conexión (>10 minutos)
**Solución:** Ya resuelto con BULK INSERT optimizado

### Error: "Access Denied" (403)

**Causa:** API key sin permisos para la entidad
**Solución:** Deshabilitar entidad o solicitar permisos en Freshsale

### Error: "Invalid column name"

**Causa:** Desajuste entre schema SQL Server y código Python
**Solución:** Ya corregido para todas las entidades

### Error: "String data, right truncation"

**Causa:** Campo NVARCHAR con límite insuficiente
**Solución:** Cambiado a NVARCHAR(MAX) en campos de texto largo

## 🔄 Migración/Actualización

### Actualizar a Nuevo Servidor SQL

```bash
# 1. Editar .env con nuevas credenciales
nano .env

# 2. Crear schema en nuevo servidor
python main.py  # Creará tablas automáticamente

# 3. Carga completa inicial
python main.py --full
```

### Agregar Nueva Entidad

1. Agregar configuración en `config.py`
2. Crear método `extract_ENTITY()` en `freshsale_extractor.py`
3. Crear función `upsert_ENTITY()` en `sql_loader_extended.py`
4. Agregar mapeo en `main.py` (secciones extract y load)

## 📈 Métricas de Rendimiento

| Métrica | Valor |
|---------|-------|
| **Total entidades activas** | 8 |
| **Registros totales** | 19,618 |
| **Tiempo carga completa** | ~16 minutos |
| **Tiempo carga incremental** | <1 minuto (promedio) |
| **API requests (full load)** | ~206 |
| **Tasa de éxito** | 99.87% |

## 🔒 Seguridad

- **Credenciales** en `.env` (no versionado en Git)
- **Conexión SSL/TLS** a SQL Server (TrustServerCertificate=yes)
- **API Token** en headers (no en URL)
- **Rollback automático** en caso de error (integridad de datos)

## 📞 Soporte

1. Revisar `etl_freshsale.log`
2. Consultar tabla `freshsale.etl_control`
3. Ejecutar con `LOG_LEVEL=DEBUG` en `.env`

---

**Versión:** 2.0.0 (BULK INSERT Optimizado)
**Última actualización:** 06 Febrero 2026
**Desarrollado para:** Movigoo Innovación SPA
=======
# FreshSale_Movigoo
API y ETL de FreshSales a SQL Server 
>>>>>>> a141e47a6f91aac9d2b120ea9f3c379403a5b5a1
