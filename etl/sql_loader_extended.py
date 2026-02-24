"""
Extensión del SQL Loader con métodos para todas las entidades
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def upsert_contacts(loader, contacts: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza contacts usando BULK INSERT con tabla temporal"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not contacts:
        logger.info("No contacts to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        logger.info(f"Creating temp table for {len(contacts)} contacts...")
        cursor.execute("""
            CREATE TABLE #temp_contacts (
                id BIGINT,
                first_name NVARCHAR(100),
                last_name NVARCHAR(100),
                display_name NVARCHAR(200),
                email NVARCHAR(255),
                mobile_number NVARCHAR(50),
                work_number NVARCHAR(50),
                job_title NVARCHAR(200),
                address NVARCHAR(MAX),
                city NVARCHAR(100),
                state NVARCHAR(100),
                zipcode NVARCHAR(20),
                country NVARCHAR(100),
                owner_id BIGINT,
                sales_account_id BIGINT,
                created_at DATETIME2,
                updated_at DATETIME2,
                is_deleted BIT
            )
        """)

        logger.info("Preparing data for bulk insert...")
        insert_data = []
        for contact in contacts:
            try:
                created_at = loader.parse_date(contact.get("created_at"))
                updated_at = loader.parse_date(contact.get("updated_at"))
                insert_data.append((
                    contact["id"], contact.get("first_name"), contact.get("last_name"),
                    contact.get("display_name"), contact.get("email"),
                    contact.get("mobile_number"), contact.get("work_number"),
                    contact.get("job_title"), contact.get("address"),
                    contact.get("city"), contact.get("state"),
                    contact.get("zipcode"), contact.get("country"),
                    contact.get("owner_id"), contact.get("sales_account_id"),
                    created_at, updated_at, contact.get("is_deleted", False)
                ))
            except Exception as e:
                logger.error(f"Failed to prepare contact {contact.get('id')}: {str(e)}")
                stats["failed"] += 1

        if insert_data:
            logger.info(f"Bulk inserting {len(insert_data)} contacts to temp table...")
            loader._bulk_insert(cursor, "#temp_contacts", [
                "id","first_name","last_name","display_name","email","mobile_number",
                "work_number","job_title","address","city","state","zipcode","country",
                "owner_id","sales_account_id","created_at","updated_at","is_deleted"
            ], insert_data)

        logger.info("Executing MERGE operation...")
        cursor.execute("""
            MERGE freshsale.contacts AS target
            USING #temp_contacts AS source
            ON target.id = source.id
            WHEN MATCHED THEN
                UPDATE SET
                    first_name = source.first_name,
                    last_name = source.last_name,
                    display_name = source.display_name,
                    email = source.email,
                    mobile_number = source.mobile_number,
                    work_number = source.work_number,
                    job_title = source.job_title,
                    address = source.address,
                    city = source.city,
                    state = source.state,
                    zipcode = source.zipcode,
                    country = source.country,
                    owner_id = source.owner_id,
                    sales_account_id = source.sales_account_id,
                    created_at = source.created_at,
                    updated_at = source.updated_at,
                    is_deleted = source.is_deleted,
                    etl_updated_at = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (id, first_name, last_name, display_name, email, mobile_number,
                        work_number, job_title, address, city, state, zipcode, country,
                        owner_id, sales_account_id, created_at, updated_at, is_deleted)
                VALUES (source.id, source.first_name, source.last_name, source.display_name,
                        source.email, source.mobile_number, source.work_number,
                        source.job_title, source.address, source.city, source.state,
                        source.zipcode, source.country, source.owner_id,
                        source.sales_account_id, source.created_at, source.updated_at,
                        source.is_deleted)
            OUTPUT $action;
        """)

        merge_results = cursor.fetchall()
        for result in merge_results:
            action = result[0]
            if action == 'INSERT':
                stats["inserted"] += 1
            elif action == 'UPDATE':
                stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_contacts")
        loader.connection.commit()
        logger.info(f"Contacts loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load contacts: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(contacts)
    finally:
        cursor.close()

    return stats


def upsert_sales_accounts(loader, accounts: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza sales accounts usando BULK INSERT con tabla temporal"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not accounts:
        logger.info("No sales accounts to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        # 1. Crear tabla temporal
        logger.info(f"Creating temp table for {len(accounts)} accounts...")
        cursor.execute("""
            CREATE TABLE #temp_sales_accounts (
                id BIGINT,
                name NVARCHAR(255),
                address NVARCHAR(MAX),
                city NVARCHAR(100),
                state NVARCHAR(100),
                zipcode NVARCHAR(20),
                country NVARCHAR(100),
                industry_type_id BIGINT,
                business_type_id BIGINT,
                number_of_employees INT,
                annual_revenue FLOAT,
                website NVARCHAR(500),
                phone NVARCHAR(50),
                owner_id BIGINT,
                facebook NVARCHAR(500),
                twitter NVARCHAR(500),
                linkedin NVARCHAR(500),
                territory_id BIGINT,
                created_at DATETIME2,
                updated_at DATETIME2,
                is_deleted BIT
            )
        """)

        # 2. Preparar datos para bulk insert
        logger.info("Preparing data for bulk insert...")
        insert_data = []
        for account in accounts:
            try:
                created_at = loader.parse_date(account.get("created_at"))
                updated_at = loader.parse_date(account.get("updated_at"))

                insert_data.append((
                    account["id"], account.get("name"), account.get("address"),
                    account.get("city"), account.get("state"),
                    account.get("zipcode"), account.get("country"),
                    account.get("industry_type_id"), account.get("business_type_id"),
                    account.get("number_of_employees"), account.get("annual_revenue"),
                    account.get("website"), account.get("phone"),
                    account.get("owner_id"), account.get("facebook"),
                    account.get("twitter"), account.get("linkedin"),
                    account.get("territory_id"), created_at, updated_at,
                    account.get("is_deleted", False)
                ))
            except Exception as e:
                logger.error(f"Failed to prepare sales_account {account.get('id')}: {str(e)}")
                stats["failed"] += 1

        # 3. Bulk insert a tabla temporal
        if insert_data:
            logger.info(f"Bulk inserting {len(insert_data)} accounts to temp table...")
            loader._bulk_insert(cursor, "#temp_sales_accounts", [
                "id","name","address","city","state","zipcode","country",
                "industry_type_id","business_type_id","number_of_employees",
                "annual_revenue","website","phone","owner_id","facebook",
                "twitter","linkedin","territory_id","created_at","updated_at","is_deleted"
            ], insert_data)

        # 4. MERGE desde tabla temporal a tabla final
        logger.info("Executing MERGE operation...")
        cursor.execute("""
            MERGE freshsale.sales_accounts AS target
            USING #temp_sales_accounts AS source
            ON target.id = source.id
            WHEN MATCHED THEN
                UPDATE SET
                    name = source.name,
                    address = source.address,
                    city = source.city,
                    state = source.state,
                    zipcode = source.zipcode,
                    country = source.country,
                    industry_type_id = source.industry_type_id,
                    business_type_id = source.business_type_id,
                    number_of_employees = source.number_of_employees,
                    annual_revenue = source.annual_revenue,
                    website = source.website,
                    phone = source.phone,
                    owner_id = source.owner_id,
                    facebook = source.facebook,
                    twitter = source.twitter,
                    linkedin = source.linkedin,
                    territory_id = source.territory_id,
                    created_at = source.created_at,
                    updated_at = source.updated_at,
                    is_deleted = source.is_deleted,
                    etl_updated_at = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (id, name, address, city, state, zipcode, country,
                        industry_type_id, business_type_id, number_of_employees,
                        annual_revenue, website, phone, owner_id, facebook,
                        twitter, linkedin, territory_id, created_at, updated_at, is_deleted)
                VALUES (source.id, source.name, source.address, source.city,
                        source.state, source.zipcode, source.country,
                        source.industry_type_id, source.business_type_id,
                        source.number_of_employees, source.annual_revenue,
                        source.website, source.phone, source.owner_id,
                        source.facebook, source.twitter, source.linkedin,
                        source.territory_id, source.created_at, source.updated_at,
                        source.is_deleted)
            OUTPUT $action;
        """)

        # Contar resultados del MERGE
        merge_results = cursor.fetchall()
        for result in merge_results:
            action = result[0]
            if action == 'INSERT':
                stats["inserted"] += 1
            elif action == 'UPDATE':
                stats["updated"] += 1

        # 5. Limpiar tabla temporal
        cursor.execute("DROP TABLE #temp_sales_accounts")

        # 6. Commit
        loader.connection.commit()
        logger.info(f"Sales accounts loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load sales accounts: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(accounts)
    finally:
        cursor.close()

    return stats


def upsert_tasks(loader, tasks: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza tasks usando BULK INSERT con tabla temporal"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not tasks:
        logger.info("No tasks to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        logger.info(f"Creating temp table for {len(tasks)} tasks...")
        cursor.execute("""
            CREATE TABLE #temp_tasks (
                id BIGINT, title NVARCHAR(255), description NVARCHAR(MAX),
                due_date DATETIME2, status NVARCHAR(50), owner_id BIGINT,
                creator_id BIGINT, targetable_type NVARCHAR(50), targetable_id BIGINT,
                created_at DATETIME2, updated_at DATETIME2, completed_at DATETIME2, is_deleted BIT
            )
        """)

        logger.info("Preparing data for bulk insert...")
        insert_data = []
        for task in tasks:
            try:
                due_date = loader.parse_date(task.get("due_date"))
                created_at = loader.parse_date(task.get("created_at"))
                updated_at = loader.parse_date(task.get("updated_at"))
                completed_at = loader.parse_date(task.get("completed_at"))
                insert_data.append((
                    task["id"], task.get("title"), task.get("description"), due_date, task.get("status"),
                    task.get("owner_id"), task.get("creator_id"), task.get("targetable_type"),
                    task.get("targetable_id"), created_at, updated_at, completed_at, task.get("is_deleted", False)
                ))
            except Exception as e:
                logger.error(f"Failed to prepare task {task.get('id')}: {str(e)}")
                stats["failed"] += 1

        if insert_data:
            logger.info(f"Bulk inserting {len(insert_data)} tasks...")
            loader._bulk_insert(cursor, "#temp_tasks", [
                "id","title","description","due_date","status","owner_id",
                "creator_id","targetable_type","targetable_id","created_at","updated_at","completed_at","is_deleted"
            ], insert_data)

        logger.info("Executing MERGE...")
        cursor.execute("""
            MERGE freshsale.tasks AS target
            USING #temp_tasks AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET title = source.title, description = source.description,
                due_date = source.due_date, status = source.status, owner_id = source.owner_id,
                creator_id = source.creator_id, targetable_type = source.targetable_type,
                targetable_id = source.targetable_id, created_at = source.created_at,
                updated_at = source.updated_at, completed_at = source.completed_at,
                is_deleted = source.is_deleted, etl_updated_at = GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, title, description, due_date, status, owner_id,
                creator_id, targetable_type, targetable_id, created_at, updated_at, completed_at, is_deleted)
                VALUES (source.id, source.title, source.description, source.due_date, source.status,
                source.owner_id, source.creator_id, source.targetable_type, source.targetable_id,
                source.created_at, source.updated_at, source.completed_at, source.is_deleted)
            OUTPUT $action;
        """)

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_tasks")
        loader.connection.commit()
        logger.info(f"Tasks loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load tasks: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(tasks)
    finally:
        cursor.close()

    return stats


def upsert_appointments(loader, appointments: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza appointments usando BULK INSERT"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not appointments:
        logger.info("No appointments to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        logger.info(f"Creating temp table for {len(appointments)} appointments...")
        cursor.execute("""
            CREATE TABLE #temp_appointments (
                id BIGINT, title NVARCHAR(255), description NVARCHAR(MAX), from_date DATETIME2,
                end_date DATETIME2, time_zone NVARCHAR(100), location NVARCHAR(500),
                creator_id BIGINT, owner_id BIGINT, targetable_type NVARCHAR(50),
                targetable_id BIGINT, created_at DATETIME2, updated_at DATETIME2, is_deleted BIT
            )
        """)

        insert_data = []
        for appt in appointments:
            try:
                from_date = loader.parse_date(appt.get("from_date"))
                end_date = loader.parse_date(appt.get("end_date"))
                created_at = loader.parse_date(appt.get("created_at"))
                updated_at = loader.parse_date(appt.get("updated_at"))
                insert_data.append((
                    appt["id"], appt.get("title"), appt.get("description"), from_date, end_date,
                    appt.get("time_zone"), appt.get("location"), appt.get("creator_id"),
                    appt.get("owner_id"), appt.get("targetable_type"), appt.get("targetable_id"),
                    created_at, updated_at, appt.get("is_deleted", False)
                ))
            except Exception as e:
                logger.error(f"Failed to prepare appointment {appt.get('id')}: {str(e)}")
                stats["failed"] += 1

        if insert_data:
            loader._bulk_insert(cursor, "#temp_appointments", [
                "id","title","description","from_date","end_date","time_zone",
                "location","creator_id","owner_id","targetable_type","targetable_id","created_at","updated_at","is_deleted"
            ], insert_data)

        cursor.execute("""
            MERGE freshsale.appointments AS target
            USING #temp_appointments AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET title=source.title, description=source.description,
                from_date=source.from_date, end_date=source.end_date, time_zone=source.time_zone,
                location=source.location, creator_id=source.creator_id, owner_id=source.owner_id,
                targetable_type=source.targetable_type, targetable_id=source.targetable_id,
                created_at=source.created_at, updated_at=source.updated_at, is_deleted=source.is_deleted,
                etl_updated_at=GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, title, description, from_date, end_date, time_zone,
                location, creator_id, owner_id, targetable_type, targetable_id, created_at, updated_at, is_deleted)
                VALUES (source.id, source.title, source.description, source.from_date, source.end_date,
                source.time_zone, source.location, source.creator_id, source.owner_id, source.targetable_type,
                source.targetable_id, source.created_at, source.updated_at, source.is_deleted)
            OUTPUT $action;
        """)

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_appointments")
        loader.connection.commit()
        logger.info(f"Appointments loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load appointments: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(appointments)
    finally:
        cursor.close()

    return stats


def upsert_sales_activities(loader, activities: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza sales activities usando BULK INSERT"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not activities:
        logger.info("No sales activities to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        logger.info(f"Creating temp table for {len(activities)} activities...")
        cursor.execute("""CREATE TABLE #temp_sales_activities (
            id BIGINT, title NVARCHAR(255), description NVARCHAR(MAX), start_date DATETIME2, end_date DATETIME2,
            owner_id BIGINT, creator_id BIGINT, targetable_type NVARCHAR(50), targetable_id BIGINT,
            sales_activity_type_id BIGINT, sales_activity_outcome_id BIGINT,
            created_at DATETIME2, updated_at DATETIME2, is_deleted BIT)""")

        insert_data = []
        for activity in activities:
            try:
                start_date = loader.parse_date(activity.get("start_date"))
                end_date = loader.parse_date(activity.get("end_date"))
                created_at = loader.parse_date(activity.get("created_at"))
                updated_at = loader.parse_date(activity.get("updated_at"))
                insert_data.append((
                    activity["id"], activity.get("title"), activity.get("description"), start_date, end_date,
                    activity.get("owner_id"), activity.get("creator_id"), activity.get("targetable_type"),
                    activity.get("targetable_id"), activity.get("sales_activity_type_id"),
                    activity.get("sales_activity_outcome_id"), created_at, updated_at, activity.get("is_deleted", False)))
            except Exception as e:
                logger.error(f"Failed to prepare activity {activity.get('id')}: {str(e)}")
                stats["failed"] += 1

        if insert_data:
            loader._bulk_insert(cursor, "#temp_sales_activities", [
                "id","title","description","start_date","end_date","owner_id","creator_id","targetable_type",
                "targetable_id","sales_activity_type_id","sales_activity_outcome_id","created_at","updated_at","is_deleted"
            ], insert_data)

        cursor.execute("""MERGE freshsale.sales_activities AS target
            USING #temp_sales_activities AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET title=source.title, description=source.description,
                start_date=source.start_date, end_date=source.end_date, owner_id=source.owner_id,
                creator_id=source.creator_id, targetable_type=source.targetable_type,
                targetable_id=source.targetable_id, sales_activity_type_id=source.sales_activity_type_id,
                sales_activity_outcome_id=source.sales_activity_outcome_id,
                created_at=source.created_at, updated_at=source.updated_at, is_deleted=source.is_deleted,
                etl_updated_at=GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, title, description, start_date, end_date, owner_id,
                creator_id, targetable_type, targetable_id, sales_activity_type_id, sales_activity_outcome_id,
                created_at, updated_at, is_deleted)
                VALUES (source.id, source.title, source.description, source.start_date, source.end_date,
                source.owner_id, source.creator_id, source.targetable_type, source.targetable_id,
                source.sales_activity_type_id, source.sales_activity_outcome_id,
                source.created_at, source.updated_at, source.is_deleted)
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_sales_activities")
        loader.connection.commit()
        logger.info(f"Sales activities loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load sales activities: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(activities)
    finally:
        cursor.close()

    return stats


def upsert_leads(loader, leads: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza leads usando BULK INSERT"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not leads:
        logger.info("No leads to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        logger.info(f"Creating temp table for {len(leads)} leads...")
        cursor.execute("""CREATE TABLE #temp_leads (
            id BIGINT, first_name NVARCHAR(100), last_name NVARCHAR(100), display_name NVARCHAR(200),
            email NVARCHAR(255), mobile_number NVARCHAR(50), work_number NVARCHAR(50),
            job_title NVARCHAR(200), address NVARCHAR(MAX), city NVARCHAR(100), state NVARCHAR(100),
            zipcode NVARCHAR(20), country NVARCHAR(100), owner_id BIGINT, lead_source_id BIGINT,
            territory_id BIGINT, created_at DATETIME2, updated_at DATETIME2, is_deleted BIT)""")

        insert_data = []
        for lead in leads:
            try:
                created_at = loader.parse_date(lead.get("created_at"))
                updated_at = loader.parse_date(lead.get("updated_at"))
                insert_data.append((
                    lead["id"], lead.get("first_name"), lead.get("last_name"), lead.get("display_name"),
                    lead.get("email"), lead.get("mobile_number"), lead.get("work_number"),
                    lead.get("job_title"), lead.get("address"), lead.get("city"), lead.get("state"),
                    lead.get("zipcode"), lead.get("country"), lead.get("owner_id"),
                    lead.get("lead_source_id"), lead.get("territory_id"), created_at, updated_at,
                    lead.get("is_deleted", False)))
            except Exception as e:
                logger.error(f"Failed to prepare lead {lead.get('id')}: {str(e)}")
                stats["failed"] += 1

        if insert_data:
            loader._bulk_insert(cursor, "#temp_leads", [
                "id","first_name","last_name","display_name","email","mobile_number","work_number",
                "job_title","address","city","state","zipcode","country","owner_id","lead_source_id",
                "territory_id","created_at","updated_at","is_deleted"
            ], insert_data)

        cursor.execute("""MERGE freshsale.leads AS target
            USING #temp_leads AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET first_name=source.first_name, last_name=source.last_name,
                display_name=source.display_name, email=source.email, mobile_number=source.mobile_number,
                work_number=source.work_number, job_title=source.job_title, address=source.address,
                city=source.city, state=source.state, zipcode=source.zipcode, country=source.country,
                owner_id=source.owner_id, lead_source_id=source.lead_source_id,
                territory_id=source.territory_id, created_at=source.created_at,
                updated_at=source.updated_at, is_deleted=source.is_deleted, etl_updated_at=GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, first_name, last_name, display_name, email, mobile_number,
                work_number, job_title, address, city, state, zipcode, country, owner_id,
                lead_source_id, territory_id, created_at, updated_at, is_deleted)
                VALUES (source.id, source.first_name, source.last_name, source.display_name, source.email,
                source.mobile_number, source.work_number, source.job_title, source.address,
                source.city, source.state, source.zipcode, source.country, source.owner_id,
                source.lead_source_id, source.territory_id, source.created_at, source.updated_at,
                source.is_deleted)
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_leads")
        loader.connection.commit()
        logger.info(f"Leads loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load leads: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(leads)
    finally:
        cursor.close()

    return stats


def upsert_pipelines(loader, pipelines: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza pipelines usando BULK INSERT"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not pipelines:
        logger.info("No pipelines to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        cursor.execute("""CREATE TABLE #temp_pipelines (
            id BIGINT, name NVARCHAR(255), is_default BIT, created_at DATETIME2, updated_at DATETIME2)""")

        insert_data = []
        for pipeline in pipelines:
            try:
                created_at = loader.parse_date(pipeline.get("created_at"))
                updated_at = loader.parse_date(pipeline.get("updated_at"))
                insert_data.append((pipeline["id"], pipeline.get("name"),
                    pipeline.get("is_default", False), created_at, updated_at))
            except Exception as e:
                logger.error(f"Failed to prepare pipeline {pipeline.get('id')}: {str(e)}")
                stats["failed"] += 1

        if insert_data:
            loader._bulk_insert(cursor, "#temp_pipelines", [
                "id","name","is_default","created_at","updated_at"
            ], insert_data)

        cursor.execute("""MERGE freshsale.pipelines AS target
            USING #temp_pipelines AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET name=source.name, is_default=source.is_default,
                created_at=source.created_at, updated_at=source.updated_at, etl_updated_at=GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, name, is_default, created_at, updated_at)
                VALUES (source.id, source.name, source.is_default, source.created_at, source.updated_at)
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_pipelines")
        loader.connection.commit()
        logger.info(f"Pipelines loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load pipelines: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(pipelines)
    finally:
        cursor.close()

    return stats


def upsert_stages(loader, stages: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza stages usando BULK INSERT"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not stages:
        logger.info("No stages to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        # Tabla temporal con campos que coinciden con SQL Server
        cursor.execute("""CREATE TABLE #temp_stages (
            id BIGINT,
            name NVARCHAR(500),
            pipeline_id BIGINT,
            position BIGINT,
            probability BIGINT,
            type NVARCHAR(100),
            created_at DATETIME,
            updated_at DATETIME
        )""")

        insert_data = []
        for stage in stages:
            created_at = loader.parse_date(stage.get("created_at"))
            updated_at = loader.parse_date(stage.get("updated_at"))

            # Mapear deal_pipeline_id (API) -> pipeline_id (SQL Server)
            # Mapear forecast_type (API) -> type (SQL Server)
            insert_data.append((
                stage["id"],
                stage.get("name"),
                stage.get("deal_pipeline_id"),  # Se mapeará a pipeline_id
                stage.get("position"),
                stage.get("probability"),
                stage.get("forecast_type"),  # Se mapeará a type
                created_at,
                updated_at
            ))

        if insert_data:
            loader._bulk_insert(cursor, "#temp_stages", [
                "id","name","pipeline_id","position","probability","type","created_at","updated_at"
            ], insert_data)

        # MERGE de tabla temporal a tabla final
        cursor.execute("""MERGE freshsale.stages AS target
            USING #temp_stages AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET
                name = source.name,
                pipeline_id = source.pipeline_id,
                position = source.position,
                probability = source.probability,
                type = source.type,
                created_at = source.created_at,
                updated_at = source.updated_at,
                etl_updated_at = GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, name, pipeline_id, position, probability, type, created_at, updated_at)
                VALUES (source.id, source.name, source.pipeline_id, source.position,
                source.probability, source.type, source.created_at, source.updated_at)
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_stages")
        loader.connection.commit()
        logger.info(f"Stages loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load stages: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(stages)
    finally:
        cursor.close()

    return stats


def upsert_products(loader, products: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza products usando BULK INSERT"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not products:
        logger.info("No products to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        logger.info(f"Creating temp table for {len(products)} products...")
        # Tabla temporal con campos que coinciden con SQL Server
        cursor.execute("""CREATE TABLE #temp_products (
            id BIGINT,
            name NVARCHAR(500),
            category NVARCHAR(255),
            description NVARCHAR(MAX),
            price FLOAT,
            currency NVARCHAR(10),
            sku_number NVARCHAR(200),
            created_at DATETIME,
            updated_at DATETIME,
            is_deleted BIT
        )""")

        insert_data = []
        for product in products:
            created_at = loader.parse_date(product.get("created_at"))
            updated_at = loader.parse_date(product.get("updated_at"))

            # Mapear campos de API a SQL Server
            insert_data.append((
                product["id"],
                product.get("name"),
                product.get("category"),
                product.get("description"),
                product.get("base_currency_amount"),  # price en SQL Server
                None,  # currency - la API no devuelve este campo en pricing_type=1
                product.get("sku_number"),  # sku_number en SQL Server
                created_at,
                updated_at,
                product.get("is_deleted", False)  # is_deleted
            ))

        if insert_data:
            loader._bulk_insert(cursor, "#temp_products", [
                "id","name","category","description","price","currency","sku_number","created_at","updated_at","is_deleted"
            ], insert_data)

        # MERGE de tabla temporal a tabla final
        cursor.execute("""MERGE freshsale.products AS target
            USING #temp_products AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET
                name = source.name,
                category = source.category,
                description = source.description,
                price = source.price,
                currency = source.currency,
                sku_number = source.sku_number,
                created_at = source.created_at,
                updated_at = source.updated_at,
                is_deleted = source.is_deleted,
                etl_updated_at = GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, name, category, description, price, currency, sku_number, created_at, updated_at, is_deleted)
                VALUES (source.id, source.name, source.category, source.description, source.price, source.currency,
                        source.sku_number, source.created_at, source.updated_at, source.is_deleted)
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_products")
        loader.connection.commit()
        logger.info(f"Products loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load products: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(products)
    finally:
        cursor.close()

    return stats


def upsert_forecast_categories(loader, categories: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza forecast categories"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not categories:
        logger.info("No forecast categories to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        cursor.execute("""CREATE TABLE #temp_forecast_categories (
            id BIGINT,
            name NVARCHAR(200),
            position INT,
            is_default BIT
        )""")

        insert_data = []
        for cat in categories:
            insert_data.append((
                cat.get("id"),
                cat.get("value"),  # API usa "value" como nombre de la categoría
                cat.get("position"),
                1 if cat.get("is_default") else 0
            ))

        loader._bulk_insert(cursor, "#temp_forecast_categories", [
            "id","name","position","is_default"
        ], insert_data)

        cursor.execute("""MERGE freshsale.forecast_categories AS target
            USING #temp_forecast_categories AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET
                name = source.name,
                position = source.position,
                is_default = source.is_default,
                etl_updated_at = GETDATE()
            WHEN NOT MATCHED THEN INSERT
                (id, name, position, is_default, etl_created_at, etl_updated_at)
            VALUES
                (source.id, source.name, source.position, source.is_default, GETDATE(), GETDATE())
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_forecast_categories")
        loader.connection.commit()
        logger.info(f"Forecast categories loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to load forecast categories: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(categories)
    finally:
        cursor.close()

    return stats


def upsert_deal_predictions(loader, predictions: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza deal predictions"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not predictions:
        logger.info("No deal predictions to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        cursor.execute("""CREATE TABLE #temp_deal_predictions (
            id BIGINT,
            name NVARCHAR(200),
            position INT,
            is_default BIT
        )""")

        insert_data = []
        for pred in predictions:
            insert_data.append((
                pred.get("id"),
                pred.get("value"),  # API usa "value" como nombre de la predicción
                pred.get("position"),
                1 if pred.get("is_default") else 0
            ))

        loader._bulk_insert(cursor, "#temp_deal_predictions", [
            "id","name","position","is_default"
        ], insert_data)

        cursor.execute("""MERGE freshsale.deal_predictions AS target
            USING #temp_deal_predictions AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET
                name = source.name,
                position = source.position,
                is_default = source.is_default,
                etl_updated_at = GETDATE()
            WHEN NOT MATCHED THEN INSERT
                (id, name, position, is_default, etl_created_at, etl_updated_at)
            VALUES
                (source.id, source.name, source.position, source.is_default, GETDATE(), GETDATE())
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_deal_predictions")
        loader.connection.commit()
        logger.info(f"Deal predictions loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to load deal predictions: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(predictions)
    finally:
        cursor.close()

    return stats


def upsert_deal_products(loader, deal_products: List[Dict]) -> Dict[str, int]:
    """Inserta o actualiza deal products usando BULK INSERT"""
    stats = {"inserted": 0, "updated": 0, "failed": 0}

    if not deal_products:
        logger.info("No deal products to load")
        return stats

    cursor = loader.connection.cursor()

    try:
        cursor.execute("""CREATE TABLE #temp_deal_products (
            id BIGINT, deal_id BIGINT, product_id BIGINT, quantity FLOAT,
            unit_price FLOAT, discount FLOAT, total FLOAT, created_at DATETIME2, updated_at DATETIME2)""")

        insert_data = []
        for dp in deal_products:
            try:
                created_at = loader.parse_date(dp.get("created_at"))
                updated_at = loader.parse_date(dp.get("updated_at"))
                insert_data.append((
                    dp["id"], dp.get("deal_id"), dp.get("product_id"), dp.get("quantity"),
                    dp.get("unit_price"), dp.get("discount"), dp.get("total"), created_at, updated_at))
            except Exception as e:
                logger.error(f"Failed to prepare deal_product {dp.get('id')}: {str(e)}")
                stats["failed"] += 1

        if insert_data:
            loader._bulk_insert(cursor, "#temp_deal_products", [
                "id","deal_id","product_id","quantity","unit_price","discount","total","created_at","updated_at"
            ], insert_data)

        cursor.execute("""MERGE freshsale.deal_products AS target
            USING #temp_deal_products AS source ON target.id = source.id
            WHEN MATCHED THEN UPDATE SET deal_id=source.deal_id, product_id=source.product_id,
                quantity=source.quantity, unit_price=source.unit_price, discount=source.discount,
                total=source.total, created_at=source.created_at, updated_at=source.updated_at,
                etl_updated_at=GETDATE()
            WHEN NOT MATCHED THEN INSERT (id, deal_id, product_id, quantity, unit_price,
                discount, total, created_at, updated_at)
                VALUES (source.id, source.deal_id, source.product_id, source.quantity,
                source.unit_price, source.discount, source.total, source.created_at, source.updated_at)
            OUTPUT $action;""")

        merge_results = cursor.fetchall()
        for result in merge_results:
            if result[0] == 'INSERT': stats["inserted"] += 1
            elif result[0] == 'UPDATE': stats["updated"] += 1

        cursor.execute("DROP TABLE #temp_deal_products")
        loader.connection.commit()
        logger.info(f"Deal products loaded: {stats['inserted']} inserted, {stats['updated']} updated, {stats['failed']} failed")

    except Exception as e:
        logger.error(f"Failed to bulk load deal products: {str(e)}")
        loader.connection.rollback()
        stats["failed"] = len(deal_products)
    finally:
        cursor.close()

    return stats
