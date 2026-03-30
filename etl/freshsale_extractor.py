"""
Módulo de extracción de datos desde Freshsale API
"""

import requests
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FreshsaleExtractor:
    """Extrae datos desde la API de Freshsale"""

    def __init__(self, domain: str, api_key: str, page_size: int = 100,
                 max_retries: int = 3, retry_delay: int = 5,
                 request_timeout: int = 30, rate_limit_delay: float = 0.5):
        """
        Inicializa el extractor de Freshsale

        Args:
            domain: Dominio de Freshsale (ej: empresa.myfreshworks.com)
            api_key: API key para autenticación
            page_size: Número de registros por página
            max_retries: Número máximo de reintentos
            retry_delay: Segundos entre reintentos
            request_timeout: Timeout para requests
            rate_limit_delay: Delay entre requests
        """
        self.domain = domain
        self.api_key = api_key
        self.base_url = f"https://{domain}/crm/sales/api"
        self.page_size = page_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_timeout = request_timeout
        self.rate_limit_delay = rate_limit_delay

        self.headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }

        # Estadísticas
        self.stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_records": 0
        }

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Realiza una petición HTTP con reintentos

        Args:
            url: URL completa del endpoint
            params: Parámetros de la query string

        Returns:
            Respuesta JSON o None en caso de error
        """
        for attempt in range(self.max_retries):
            try:
                self.stats["total_requests"] += 1

                logger.debug(f"Request: {url} (attempt {attempt + 1}/{self.max_retries})")

                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=self.request_timeout
                )

                # Rate limiting
                time.sleep(self.rate_limit_delay)

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 429:
                    # Rate limit exceeded
                    wait_time = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

                elif response.status_code in [403, 401]:
                    # Permisos denegados - no reintentar
                    logger.error(f"Access denied: {response.text}")
                    self.stats["failed_requests"] += 1
                    return None

                elif response.status_code == 404:
                    # Not found - no reintentar
                    logger.warning(f"Endpoint not found: {url}")
                    self.stats["failed_requests"] += 1
                    return None

                else:
                    logger.warning(f"HTTP {response.status_code}: {response.text}")

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed on attempt {attempt + 1}: {str(e)}")

            # Esperar antes de reintentar
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        # Si llegamos aquí, todos los reintentos fallaron
        self.stats["failed_requests"] += 1
        logger.error(f"All retry attempts failed for: {url}")
        return None

    def extract_deals(self, filter_id: int, last_updated: Optional[datetime] = None,
                      extra_filter_ids: Optional[List[int]] = None) -> List[Dict]:
        """
        Extrae deals usando uno o más filtros. Deduplica por ID.

        Args:
            filter_id: ID del filtro principal
            last_updated: Fecha de última actualización para carga incremental
            extra_filter_ids: IDs de filtros adicionales (otros pipelines)

        Returns:
            Lista de deals deduplicada
        """
        all_filter_ids = [filter_id] + (extra_filter_ids or [])
        deals_by_id = {}

        for fid in all_filter_ids:
            logger.info(f"Extracting deals with filter {fid}")
            page = 1
            total_pages = None

            while True:
                url = f"{self.base_url}/deals/view/{fid}"
                params = {
                    "page": page,
                    "per_page": self.page_size,
                    "include": "products,owner,sales_account"
                }

                if last_updated:
                    params["updated_at"] = f">{last_updated.isoformat()}"

                data = self._make_request(url, params)

                if not data:
                    logger.error(f"Failed to extract deals page {page} (filter {fid})")
                    break

                deals = data.get("deals", [])
                meta = data.get("meta", {})

                for deal in deals:
                    deals_by_id[deal["id"]] = deal

                logger.info(f"Filter {fid} page {page}: {len(deals)} deals")

                if total_pages is None:
                    total_pages = meta.get("total_pages", 1)
                    total_records = meta.get("total", 0)
                    logger.info(f"Filter {fid} — Total pages: {total_pages}, Total records: {total_records}")

                if page >= total_pages or len(deals) == 0:
                    break

                page += 1

        all_deals = list(deals_by_id.values())
        logger.info(f"Total deals extracted (all pipelines, deduplicated): {len(all_deals)}")
        return all_deals

    def extract_contacts(self, filter_id: int, last_updated: Optional[datetime] = None) -> List[Dict]:
        """Extrae contactos"""
        logger.info(f"Extracting contacts with filter {filter_id}")

        all_contacts = []
        page = 1
        total_pages = None

        while True:
            url = f"{self.base_url}/contacts/view/{filter_id}"
            params = {
                "page": page,
                "per_page": self.page_size
            }

            if last_updated:
                params["updated_at"] = f">{last_updated.isoformat()}"

            data = self._make_request(url, params)

            if not data:
                logger.error(f"Failed to extract contacts page {page}")
                break

            contacts = data.get("contacts", [])
            meta = data.get("meta", {})

            all_contacts.extend(contacts)
            self.stats["total_records"] += len(contacts)

            logger.info(f"Extracted page {page}: {len(contacts)} contacts")

            if total_pages is None:
                total_pages = meta.get("total_pages", 1)
                logger.info(f"Total pages: {total_pages}")

            if page >= total_pages or len(contacts) == 0:
                break

            page += 1

        logger.info(f"Total contacts extracted: {len(all_contacts)}")
        return all_contacts

    def extract_tasks(self, last_updated: Optional[datetime] = None) -> List[Dict]:
        """Extrae tareas"""
        logger.info("Extracting tasks")

        all_tasks = []
        page = 1

        while True:
            url = f"{self.base_url}/tasks"
            params = {
                "page": page,
                "per_page": self.page_size
            }

            if last_updated:
                params["updated_at"] = f">{last_updated.isoformat()}"

            data = self._make_request(url, params)

            if not data:
                logger.error(f"Failed to extract tasks page {page}")
                break

            tasks = data.get("tasks", [])
            meta = data.get("meta", {})

            all_tasks.extend(tasks)
            self.stats["total_records"] += len(tasks)

            logger.info(f"Extracted page {page}: {len(tasks)} tasks")

            if len(tasks) == 0:
                break

            page += 1

        logger.info(f"Total tasks extracted: {len(all_tasks)}")
        return all_tasks

    def extract_appointments(self, last_updated: Optional[datetime] = None) -> List[Dict]:
        """Extrae citas"""
        logger.info("Extracting appointments")

        all_appointments = []
        page = 1

        while True:
            url = f"{self.base_url}/appointments"
            params = {
                "page": page,
                "per_page": self.page_size
            }

            if last_updated:
                params["updated_at"] = f">{last_updated.isoformat()}"

            data = self._make_request(url, params)

            if not data:
                logger.error(f"Failed to extract appointments page {page}")
                break

            appointments = data.get("appointments", [])

            all_appointments.extend(appointments)
            self.stats["total_records"] += len(appointments)

            logger.info(f"Extracted page {page}: {len(appointments)} appointments")

            if len(appointments) == 0:
                break

            page += 1

        logger.info(f"Total appointments extracted: {len(all_appointments)}")
        return all_appointments

    def extract_sales_activities(self, last_updated: Optional[datetime] = None) -> List[Dict]:
        """Extrae actividades de ventas"""
        logger.info("Extracting sales activities")

        all_activities = []
        page = 1

        while True:
            url = f"{self.base_url}/sales_activities"
            params = {
                "page": page,
                "per_page": self.page_size
            }

            if last_updated:
                params["updated_at"] = f">{last_updated.isoformat()}"

            data = self._make_request(url, params)

            if not data:
                logger.error(f"Failed to extract sales activities page {page}")
                break

            activities = data.get("sales_activities", [])

            all_activities.extend(activities)
            self.stats["total_records"] += len(activities)

            logger.info(f"Extracted page {page}: {len(activities)} activities")

            if len(activities) == 0:
                break

            page += 1

        logger.info(f"Total sales activities extracted: {len(all_activities)}")
        return all_activities

    def extract_users(self) -> List[Dict]:
        """Extrae usuarios"""
        logger.info("Extracting users")

        url = f"{self.base_url}/selector/owners"
        data = self._make_request(url)

        if not data:
            logger.error("Failed to extract users")
            return []

        users = data.get("users", [])
        self.stats["total_records"] += len(users)

        logger.info(f"Total users extracted: {len(users)}")
        return users

    def extract_teams(self) -> List[Dict]:
        """Extrae equipos"""
        logger.info("Extracting teams")

        url = f"{self.base_url}/selector/teams"
        data = self._make_request(url)

        if not data:
            logger.error("Failed to extract teams")
            return []

        teams = data.get("teams", [])
        self.stats["total_records"] += len(teams)

        logger.info(f"Total teams extracted: {len(teams)}")
        return teams

    def extract_leads(self, filter_id: int, last_updated: Optional[datetime] = None) -> List[Dict]:
        """Extrae leads"""
        logger.info(f"Extracting leads with filter {filter_id}")

        all_leads = []
        page = 1
        total_pages = None

        while True:
            url = f"{self.base_url}/leads/view/{filter_id}"
            params = {
                "page": page,
                "per_page": self.page_size
            }

            if last_updated:
                params["updated_at"] = f">{last_updated.isoformat()}"

            data = self._make_request(url, params)

            if not data:
                logger.error(f"Failed to extract leads page {page}")
                break

            leads = data.get("leads", [])
            meta = data.get("meta", {})

            all_leads.extend(leads)
            self.stats["total_records"] += len(leads)

            logger.info(f"Extracted page {page}: {len(leads)} leads")

            if total_pages is None:
                total_pages = meta.get("total_pages", 1)
                logger.info(f"Total pages: {total_pages}")

            if page >= total_pages or len(leads) == 0:
                break

            page += 1

        logger.info(f"Total leads extracted: {len(all_leads)}")
        return all_leads

    def extract_sales_accounts(self, filter_id: int, last_updated: Optional[datetime] = None) -> List[Dict]:
        """Extrae sales accounts"""
        logger.info(f"Extracting sales accounts with filter {filter_id}")

        all_accounts = []
        page = 1
        total_pages = None

        while True:
            url = f"{self.base_url}/sales_accounts/view/{filter_id}"
            params = {
                "page": page,
                "per_page": self.page_size
            }

            if last_updated:
                params["updated_at"] = f">{last_updated.isoformat()}"

            data = self._make_request(url, params)

            if not data:
                logger.error(f"Failed to extract sales accounts page {page}")
                break

            accounts = data.get("sales_accounts", [])
            meta = data.get("meta", {})

            all_accounts.extend(accounts)
            self.stats["total_records"] += len(accounts)

            logger.info(f"Extracted page {page}: {len(accounts)} sales accounts")

            if total_pages is None:
                total_pages = meta.get("total_pages", 1)
                logger.info(f"Total pages: {total_pages}")

            if page >= total_pages or len(accounts) == 0:
                break

            page += 1

        logger.info(f"Total sales accounts extracted: {len(all_accounts)}")
        return all_accounts

    def extract_pipelines(self) -> List[Dict]:
        """Extrae pipelines"""
        logger.info("Extracting pipelines")

        url = f"{self.base_url}/selector/deal_pipelines"
        data = self._make_request(url)

        if not data:
            logger.error("Failed to extract pipelines")
            return []

        pipelines = data.get("deal_pipelines", [])
        self.stats["total_records"] += len(pipelines)

        logger.info(f"Total pipelines extracted: {len(pipelines)}")
        return pipelines

    def extract_stages(self, pipeline_id: int) -> List[Dict]:
        """Extrae stages de un pipeline"""
        logger.info(f"Extracting stages for pipeline {pipeline_id}")

        url = f"{self.base_url}/selector/deal_pipelines/{pipeline_id}"
        data = self._make_request(url)

        if not data:
            logger.error(f"Failed to extract stages for pipeline {pipeline_id}")
            return []

        pipeline = data.get("deal_pipeline", {})
        stages = pipeline.get("deal_stages", [])
        self.stats["total_records"] += len(stages)

        logger.info(f"Total stages extracted for pipeline {pipeline_id}: {len(stages)}")
        return stages

    def extract_products(self, last_updated: Optional[datetime] = None) -> List[Dict]:
        """Extrae products usando el endpoint CPQ correcto"""
        logger.info("Extracting products")

        all_products = []
        page = 1

        while True:
            # Endpoint correcto para products es /api/cpq/products
            url = f"{self.base_url}/cpq/products"
            params = {
                "page": page,
                "per_page": self.page_size
            }

            if last_updated:
                params["updated_at"] = f">{last_updated.isoformat()}"

            data = self._make_request(url, params)

            if not data:
                logger.error(f"Failed to extract products page {page}")
                break

            products = data.get("products", [])

            # Verificar metadata para paginación
            meta = data.get("meta", {})
            total_pages = meta.get("total_pages", 1)

            all_products.extend(products)
            self.stats["total_records"] += len(products)

            logger.info(f"Extracted page {page}/{total_pages}: {len(products)} products")

            if len(products) == 0 or page >= total_pages:
                break

            page += 1

        logger.info(f"Total products extracted: {len(all_products)}")
        return all_products

    def extract_deal_fields(self) -> List[Dict]:
        """Extrae los campos de deals incluyendo forecast categories"""
        logger.info("Extracting deal fields for forecast categories")

        url = f"{self.base_url}/settings/deals/fields"
        data = self._make_request(url)

        if not data:
            logger.error("Failed to extract deal fields")
            return []

        fields = data.get("fields", [])

        # Buscar el campo forecast_category
        forecast_field = None
        for field in fields:
            if field.get("name") == "forecast_category":
                forecast_field = field
                break

        if not forecast_field:
            logger.warning("forecast_category field not found in deal fields")
            return []

        # Extraer las opciones de forecast_category (choices)
        choices = forecast_field.get("choices", [])
        logger.info(f"Total forecast categories extracted: {len(choices)}")

        self.stats["total_records"] += len(choices)
        return choices

    def extract_deal_prediction_choices(self) -> List[Dict]:
        """Extrae las opciones de deal_prediction del campo de deals"""
        logger.info("Extracting deal fields for deal prediction")

        url = f"{self.base_url}/settings/deals/fields"
        data = self._make_request(url)

        if not data:
            logger.error("Failed to extract deal fields")
            return []

        fields = data.get("fields", [])

        # Buscar el campo deal_prediction
        prediction_field = None
        for field in fields:
            if field.get("name") == "deal_prediction":
                prediction_field = field
                break

        if not prediction_field:
            logger.warning("deal_prediction field not found in deal fields")
            return []

        # Extraer las opciones de deal_prediction (choices)
        choices = prediction_field.get("choices", [])
        logger.info(f"Total deal predictions extracted: {len(choices)}")

        self.stats["total_records"] += len(choices)
        return choices

    def extract_deal_products(self, deal_id: int) -> List[Dict]:
        """Extrae productos asociados a un deal"""
        logger.info(f"Extracting products for deal {deal_id}")

        url = f"{self.base_url}/deals/{deal_id}"
        data = self._make_request(url)

        if not data:
            logger.error(f"Failed to extract deal {deal_id}")
            return []

        deal = data.get("deal", {})
        products = deal.get("deal_products", [])
        self.stats["total_records"] += len(products)

        return products

    def get_stats(self) -> Dict[str, int]:
        """Retorna estadísticas de extracción"""
        return self.stats.copy()

    def reset_stats(self):
        """Resetea estadísticas"""
        self.stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_records": 0
        }
