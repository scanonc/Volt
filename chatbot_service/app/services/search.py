from decimal import Decimal, InvalidOperation
import logging
from typing import Any, Dict, List, Optional
import numpy as np

from app.db.repositories import ProductRepository
from app.providers.base import EmbeddingProvider
from app.services.indexer import validate_embedding_vector

logger = logging.getLogger(__name__)

VALID_SIZES = {'XS', 'S', 'M', 'L', 'XL'}
VALID_GENDERS = {'hombre', 'mujer', 'unisex'}
VALID_STYLES = {'casual', 'deportivo', 'elegante', 'urbano'}


def sanitize_filters(raw_filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Limpia y valida filtros extraídos por el LLM descartando valores fuera de catálogo/enums."""
    if not isinstance(raw_filters, dict):
        return {}

    cleaned: Dict[str, Any] = {}

    for price_key in ('min_price', 'max_price'):
        val = raw_filters.get(price_key)
        if val is not None and val != '' and not isinstance(val, bool):
            try:
                dec_val = Decimal(str(val))
                if dec_val >= 0:
                    cleaned[price_key] = dec_val
            except (InvalidOperation, ValueError, TypeError):
                pass

    cat = raw_filters.get('category')
    if isinstance(cat, str) and cat.strip():
        cleaned['category'] = cat.strip()

    color = raw_filters.get('color')
    if isinstance(color, str) and color.strip():
        cleaned['color'] = color.strip().lower()

    size = raw_filters.get('size')
    if isinstance(size, str) and size.strip().upper() in VALID_SIZES:
        cleaned['size'] = size.strip().upper()

    gender = raw_filters.get('gender')
    if isinstance(gender, str) and gender.strip().lower() in VALID_GENDERS:
        cleaned['gender'] = gender.strip().lower()

    style = raw_filters.get('style')
    if isinstance(style, str) and style.strip().lower() in VALID_STYLES:
        cleaned['style'] = style.strip().lower()

    return cleaned


def matches_strict_filters(product: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Evalúa los filtros estrictos sobre los datos frescos de un producto de Django."""
    if not filters:
        return True

    # Precio
    try:
        price = Decimal(str(product.get('price', '0')))
    except (InvalidOperation, ValueError, TypeError):
        return False

    if 'min_price' in filters and price < filters['min_price']:
        return False
    if 'max_price' in filters and price > filters['max_price']:
        return False

    # Categoría (comparación insensible a mayúsculas con Category.name)
    if 'category' in filters:
        raw_cat = product.get('category')
        prod_cat = (
            str(raw_cat.get('name') or '').strip().lower()
            if isinstance(raw_cat, dict)
            else str(raw_cat or '').strip().lower()
        )
        target_cat = filters['category'].lower()
        if not prod_cat or (target_cat != prod_cat and target_cat not in prod_cat):
            return False

    # Color (case-insensitive)
    if 'color' in filters:
        prod_color = str(product.get('color') or '').strip().lower()
        target_color = filters['color']
        if not prod_color or (target_color != prod_color and target_color not in prod_color):
            return False

    # Talla (debe estar en available_sizes)
    if 'size' in filters:
        raw_sizes = product.get('available_sizes') or []
        prod_sizes = {str(s).strip().upper() for s in raw_sizes if str(s).strip()}
        if filters['size'] not in prod_sizes:
            return False

    # Género (si el usuario pide hombre o mujer, también se acepta unisex)
    if 'gender' in filters:
        prod_gender = str(product.get('gender') or '').strip().lower()
        target_gender = filters['gender']
        if target_gender in ('hombre', 'mujer'):
            if prod_gender not in (target_gender, 'unisex'):
                return False
        else:
            if prod_gender != 'unisex':
                return False

    # Estilo
    if 'style' in filters:
        prod_style = str(product.get('style') or '').strip().lower()
        if prod_style != filters['style']:
            return False

    return True


class SearchService:
    """Servicio de búsqueda híbrida: similitud coseno en NumPy + validación con datos frescos de Django."""

    def __init__(
        self,
        product_repo: ProductRepository,
        catalog_client: Any,
        embedding_provider: EmbeddingProvider,
        similarity_threshold: float = 0.55,
        top_k: int = 10,
        max_results: int = 4,
        embedding_dim: int = 768,
    ):
        self.product_repo = product_repo
        self.catalog_client = catalog_client
        self.embedding_provider = embedding_provider
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self.max_results = max_results
        self.embedding_dim = embedding_dim

    def search(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ejecuta la búsqueda híbrida para una consulta de usuario.

        Pasos:
        1. Genera y normaliza el embedding de la consulta.
        2. Calcula similitud coseno vectorizada con NumPy contra el índice SQLite.
        3. Toma los top-K candidatos.
        4. Consulta datos frescos a Django por IDs (descarta eliminados).
        5. Aplica umbral de similitud y filtros estrictos sobre campos reales.
        6. Separa disponibles (stock > 0) de agotados (stock == 0).
        """
        clean_filters = sanitize_filters(filters)

        if not query_text or not query_text.strip():
            return {
                'status': 'no_results',
                'products': [],
                'out_of_stock': [],
                'applied_filters': clean_filters,
            }

        indexed_rows = self.product_repo.get_all_embeddings()
        if not indexed_rows:
            return {
                'status': 'no_results',
                'products': [],
                'out_of_stock': [],
                'applied_filters': clean_filters,
            }

        raw_query_vec = self.embedding_provider.embed_query(query_text.strip())
        valid_query_vec = validate_embedding_vector(raw_query_vec, self.embedding_dim)
        q_vec = np.asarray(valid_query_vec, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        # Filtrar filas con dimensión compatible
        valid_rows = [
            r for r in indexed_rows
            if isinstance(r.get('embedding'), list) and len(r['embedding']) == self.embedding_dim
        ]
        if not valid_rows:
            return {
                'status': 'no_results',
                'products': [],
                'out_of_stock': [],
                'applied_filters': clean_filters,
            }

        # Cálculo vectorizado de similitud por coseno
        matrix = np.asarray([r['embedding'] for r in valid_rows], dtype=np.float32)
        row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        normalized_matrix = np.divide(matrix, row_norms, out=np.zeros_like(matrix), where=row_norms > 0)
        scores = normalized_matrix @ q_vec

        # Ordenar de mayor a menor similitud y seleccionar top-K
        sorted_indices = np.argsort(scores)[::-1][: self.top_k]
        ranked_candidates = [
            (int(valid_rows[idx]['product_id']), float(scores[idx]))
            for idx in sorted_indices
        ]

        candidate_ids = [pid for pid, _ in ranked_candidates]
        fresh_products = self.catalog_client.get_products_by_ids(candidate_ids)
        fresh_by_id = {int(p['id']): p for p in fresh_products if isinstance(p, dict) and 'id' in p}

        available_matches: List[Dict[str, Any]] = []
        out_of_stock_matches: List[Dict[str, Any]] = []

        # Recorrer en orden de relevancia semántica
        for pid, score in ranked_candidates:
            if score < self.similarity_threshold:
                continue

            product = fresh_by_id.get(pid)
            if product is None:
                # Producto eliminado en Django aunque siga en el índice local
                continue

            if not matches_strict_filters(product, clean_filters):
                continue

            enriched = dict(product)
            enriched['similarity_score'] = round(score, 4)

            stock = int(product.get('stock') or 0)
            if stock > 0:
                available_matches.append(enriched)
            else:
                out_of_stock_matches.append(enriched)

        final_products = available_matches[: self.max_results]
        final_out_of_stock = out_of_stock_matches[: self.max_results]

        if final_products:
            status = 'ok'
        elif final_out_of_stock:
            status = 'only_out_of_stock'
        else:
            status = 'no_results'

        return {
            'status': status,
            'products': final_products,
            'out_of_stock': final_out_of_stock,
            'applied_filters': clean_filters,
        }
