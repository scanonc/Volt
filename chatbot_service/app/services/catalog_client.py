from copy import deepcopy
import logging
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class CatalogClientError(Exception):
    """Excepción base para comunicación con el catálogo de Django."""
    pass


class CatalogClientTimeoutError(CatalogClientError):
    """Timeout al consultar el catálogo."""
    pass


class CatalogClientNotFoundError(CatalogClientError):
    """Producto o recurso no encontrado."""
    pass


class CatalogClientUnavailableError(CatalogClientError):
    """Servicio de Django no disponible o error 5xx."""
    pass


class CatalogClient:
    """Cliente HTTP para consultar el catálogo de Django."""

    def __init__(self, base_url: str = 'http://django:8000', timeout: float = 2.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Consulta el detalle fresco de un producto por ID."""
        url = f"{self.base_url}/api/v1/products/{product_id}/"
        try:
            resp = requests.get(url, timeout=self.timeout)
        except requests.Timeout as exc:
            raise CatalogClientTimeoutError(f"Timeout al consultar producto {product_id} en Django") from exc
        except requests.RequestException as exc:
            raise CatalogClientUnavailableError(f"No se pudo conectar con Django en {url}: {exc}") from exc

        if resp.status_code == 404:
            return None

        if resp.status_code != 200:
            if resp.status_code >= 500:
                raise CatalogClientUnavailableError(f"Django retornó error {resp.status_code} para producto {product_id}")
            raise CatalogClientError(f"Error inesperado ({resp.status_code}) al consultar producto {product_id}: {resp.text}")

        try:
            return resp.json()
        except ValueError as exc:
            raise CatalogClientError(f"Respuesta inválida de Django (no JSON): {resp.text}") from exc

    def get_products_by_ids(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        """Consulta datos frescos de una lista de IDs de productos."""
        if not product_ids:
            return []

        ids_param = ",".join(str(pid) for pid in product_ids)
        url = f"{self.base_url}/api/v1/products/?ids={ids_param}"
        try:
            resp = requests.get(url, timeout=self.timeout)
        except requests.Timeout as exc:
            raise CatalogClientTimeoutError("Timeout al consultar productos por IDs en Django") from exc
        except requests.RequestException as exc:
            raise CatalogClientUnavailableError(f"No se pudo conectar con Django en {url}: {exc}") from exc

        if resp.status_code != 200:
            if resp.status_code >= 500:
                raise CatalogClientUnavailableError(f"Django retornó error {resp.status_code} al consultar IDs")
            raise CatalogClientError(f"Error inesperado ({resp.status_code}) al consultar productos por IDs")

        try:
            data = resp.json()
            if not isinstance(data, list):
                raise CatalogClientError("Formato de respuesta inesperado: se esperaba una lista JSON.")
            return data
        except ValueError as exc:
            raise CatalogClientError(f"Respuesta inválida de Django (no JSON): {resp.text}") from exc

    def list_products(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Lista paginada de productos para la indexación inicial."""
        url = f"{self.base_url}/api/v1/products/?limit={limit}&offset={offset}"
        try:
            resp = requests.get(url, timeout=self.timeout)
        except requests.Timeout as exc:
            raise CatalogClientTimeoutError("Timeout al paginar catálogo en Django") from exc
        except requests.RequestException as exc:
            raise CatalogClientUnavailableError(f"No se pudo conectar con Django en {url}: {exc}") from exc

        if resp.status_code != 200:
            if resp.status_code >= 500:
                raise CatalogClientUnavailableError(f"Django retornó error {resp.status_code} al paginar")
            raise CatalogClientError(f"Error inesperado ({resp.status_code}) al paginar productos")

        try:
            data = resp.json()
            if not isinstance(data, list):
                raise CatalogClientError("Formato de respuesta inesperado: se esperaba una lista JSON.")
            return data
        except ValueError as exc:
            raise CatalogClientError(f"Respuesta inválida de Django (no JSON): {resp.text}") from exc


class FakeCatalogClient:
    """Cliente simulado de catálogo para pruebas unitarias sin dependencias externas."""

    def __init__(self, initial_products: Optional[List[Dict[str, Any]]] = None):
        self.products: Dict[int, Dict[str, Any]] = {}
        if initial_products:
            for p in initial_products:
                self.products[p['id']] = deepcopy(p)

    def add_product(self, product: Dict[str, Any]) -> None:
        self.products[product['id']] = deepcopy(product)

    def remove_product(self, product_id: int) -> None:
        self.products.pop(product_id, None)

    def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        if product_id in self.products:
            return deepcopy(self.products[product_id])
        return None

    def get_products_by_ids(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        return [deepcopy(self.products[pid]) for pid in product_ids if pid in self.products]

    def list_products(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        sorted_products = [self.products[k] for k in sorted(self.products.keys())]
        slice_result = sorted_products[offset : offset + limit]
        return [deepcopy(p) for p in slice_result]
