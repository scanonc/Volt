import hashlib
import logging
import math
from typing import Any, Dict, List, Optional, Set

from app.db.repositories import ProductRepository
from app.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class InvalidEmbeddingError(ValueError):
    """Se lanza cuando el proveedor devuelve un vector vacío, nulo o de dimensión incorrecta."""
    pass


def _extract_product_fields(product: Dict[str, Any]) -> Dict[str, Any]:
    """Extrae y normaliza los campos semánticos relevantes de un producto (sin precio ni stock)."""
    name = str(product.get('name') or '').strip()

    raw_cat = product.get('category')
    if isinstance(raw_cat, dict):
        category_name = str(raw_cat.get('name') or '').strip()
    else:
        category_name = str(raw_cat or '').strip()

    description = str(product.get('description') or '').strip()
    color = str(product.get('color') or '').strip().lower()
    material = str(product.get('material') or '').strip()
    gender = str(product.get('gender') or '').strip().lower()
    style = str(product.get('style') or '').strip().lower()

    raw_sizes = product.get('available_sizes') or []
    if isinstance(raw_sizes, list):
        sizes = sorted({str(s).strip().upper() for s in raw_sizes if str(s).strip()})
    else:
        sizes = []

    return {
        'name': name,
        'category_name': category_name,
        'description': description,
        'color': color,
        'material': material,
        'gender': gender,
        'style': style,
        'available_sizes': sizes,
    }


def build_embedding_text(product: Dict[str, Any]) -> str:
    """Construye el texto semántico a embeber a partir de los campos reales (excluye precio y stock)."""
    fields = _extract_product_fields(product)
    parts: List[str] = []

    if fields['name']:
        parts.append(f"Producto: {fields['name']}")
    if fields['category_name']:
        parts.append(f"Categoría: {fields['category_name']}")
    if fields['description']:
        parts.append(f"Descripción: {fields['description']}")
    if fields['color']:
        parts.append(f"Color: {fields['color']}")
    if fields['material']:
        parts.append(f"Material: {fields['material']}")
    if fields['gender']:
        parts.append(f"Género: {fields['gender']}")
    if fields['style']:
        parts.append(f"Estilo: {fields['style']}")
    if fields['available_sizes']:
        parts.append(f"Tallas disponibles: {', '.join(fields['available_sizes'])}")

    return ". ".join(parts)


def compute_product_hash(product: Dict[str, Any]) -> str:
    """Calcula el hash SHA-256 canónico de los campos semánticos del producto."""
    fields = _extract_product_fields(product)
    canonical = "|".join([
        fields['name'],
        fields['category_name'],
        fields['description'],
        fields['color'],
        fields['material'],
        fields['gender'],
        fields['style'],
        ",".join(fields['available_sizes']),
    ])
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def validate_embedding_vector(vector: Any, expected_dim: int) -> List[float]:
    """Valida que el vector no esté vacío, tenga la dimensión esperada y valores numéricos válidos."""
    if not isinstance(vector, (list, tuple)) or len(vector) == 0:
        raise InvalidEmbeddingError("El vector de embedding está vacío o no es una lista.")

    if len(vector) != expected_dim:
        raise InvalidEmbeddingError(
            f"Dimensión de embedding inválida: se esperaba {expected_dim}, se recibió {len(vector)}."
        )

    cleaned: List[float] = []
    norm_sq = 0.0
    for val in vector:
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise InvalidEmbeddingError("El vector contiene elementos no numéricos.")
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval):
            raise InvalidEmbeddingError("El vector contiene valores NaN o infinitos.")
        cleaned.append(fval)
        norm_sq += fval * fval

    if norm_sq <= 1e-12:
        raise InvalidEmbeddingError("El vector de embedding tiene norma cero.")

    return cleaned


class IndexerService:
    """Servicio encargado de sincronizar e indexar productos del catálogo en SQLite."""

    def __init__(
        self,
        product_repo: ProductRepository,
        catalog_client: Any,
        embedding_provider: EmbeddingProvider,
        embedding_model: str = 'gemini-embedding-001',
        embedding_dim: int = 768,
    ):
        self.product_repo = product_repo
        self.catalog_client = catalog_client
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim

    def _upsert_product_dict(self, product: Dict[str, Any]) -> str:
        """Indexa un diccionario de producto si su hash o modelo cambió."""
        product_id = int(product['id'])
        new_hash = compute_product_hash(product)

        existing = self.product_repo.get(product_id)
        if (
            existing is not None
            and existing.get('content_hash') == new_hash
            and existing.get('embedding_model') == self.embedding_model
            and existing.get('embedding_dim') == self.embedding_dim
        ):
            return 'unchanged'

        text = build_embedding_text(product)
        if not text.strip():
            raise InvalidEmbeddingError(f"El producto {product_id} no tiene texto semántico para indexar.")

        raw_vector = self.embedding_provider.embed_document(text)
        valid_vector = validate_embedding_vector(raw_vector, self.embedding_dim)

        self.product_repo.upsert(
            product_id=product_id,
            content_hash=new_hash,
            embedding=valid_vector,
            model=self.embedding_model,
            dim=self.embedding_dim,
        )
        return 'indexed'

    def upsert_product(self, product_id: int) -> str:
        """Consulta el producto en Django y actualiza su embedding solo si cambió el texto relevante.

        Retorna:
            'indexed': se generó y guardó un nuevo embedding.
            'unchanged': el hash y modelo coinciden; no se llamó a Gemini.
            'deleted_missing': el producto ya no existe en Django (404) y fue eliminado del índice.
        """
        product = self.catalog_client.get_product(product_id)
        if product is None:
            self.product_repo.delete(product_id)
            return 'deleted_missing'

        return self._upsert_product_dict(product)

    def delete_product(self, product_id: int) -> bool:
        """Elimina un producto del índice local."""
        return self.product_repo.delete(product_id)

    def reindex_catalog(self, page_size: int = 50) -> Dict[str, int]:
        """Reindexación completa paginada del catálogo de Django y limpieza de productos obsoletos."""
        offset = 0
        seen_ids: Set[int] = set()
        indexed_count = 0
        unchanged_count = 0

        while True:
            batch = self.catalog_client.list_products(limit=page_size, offset=offset)
            if not batch:
                break

            for product in batch:
                pid = int(product['id'])
                seen_ids.add(pid)
                status = self._upsert_product_dict(product)
                if status == 'indexed':
                    indexed_count += 1
                elif status == 'unchanged':
                    unchanged_count += 1

            if len(batch) < page_size:
                break
            offset += page_size

        # Eliminar del índice local productos que ya no existen en Django
        current_indexed_ids = self.product_repo.get_all_product_ids()
        stale_ids = current_indexed_ids - seen_ids
        deleted_count = 0
        for stale_id in stale_ids:
            if self.product_repo.delete(stale_id):
                deleted_count += 1

        return {
            'indexed': indexed_count,
            'unchanged': unchanged_count,
            'deleted': deleted_count,
            'total_seen': len(seen_ids),
        }
