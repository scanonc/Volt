import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.db.repositories import ConversationRepository
from app.providers.base import TextGenerator
from app.services.search import SearchService, sanitize_filters

logger = logging.getLogger(__name__)


class ConversationNotFoundError(Exception):
    """Se lanza cuando se solicita un conversation_id que no existe en SQLite."""
    pass


EXTRACTION_SYSTEM_PROMPT = (
    "Eres el módulo extractor de intención y filtros de la tienda de ropa Volt. "
    "Analiza el historial reciente y el mensaje del usuario y devuelve ÚNICAMENTE un objeto JSON válido "
    "(sin texto adicional ni bloques markdown) con las claves exactas:\n"
    '{"search_text": string, "min_price": number|null, "max_price": number|null, '
    '"category": string|null, "color": string|null, "size": "XS"|"S"|"M"|"L"|"XL"|null, '
    '"gender": "hombre"|"mujer"|"unisex"|null, '
    '"style": "casual"|"deportivo"|"elegante"|"urbano"|null}\n'
    "Si un filtro no se menciona explícitamente, usa null. En search_text resume la búsqueda semántica."
)

ADVISOR_SYSTEM_PROMPT = (
    "Eres el asesor virtual de moda de Volt. Hablas en español de forma clara, amable y concisa.\n"
    "REGLAS ESTRICTAS:\n"
    "1. El catálogo proporcionado en el prompt es tu ÚNICA fuente de verdad.\n"
    "2. NUNCA inventes productos, nombres, precios, tallas, colores, materiales ni disponibilidad (stock).\n"
    "3. Solo puedes recomendar productos listados en 'PRODUCTOS DISPONIBLES DEL CATÁLOGO'.\n"
    "4. Si la lista de productos disponibles está vacía, aclara con honestidad que no encontraste prendas "
    "disponibles que cumplan todos los criterios (menciona si hay opciones agotadas cuando aparezcan en el contexto) "
    "y sugiere relajar algún filtro.\n"
    "5. Si la consulta del usuario es demasiado ambigua o insuficiente para recomendar, pide una aclaración breve "
    "(por ejemplo ocasión, estilo, clima o presupuesto)."
)


def parse_extraction_json(raw_text: str, fallback_query: str) -> Tuple[str, Dict[str, Any]]:
    """Extrae search_text y filtros desde la respuesta del LLM; si el JSON es inválido, continúa sin filtros."""
    if not raw_text or not isinstance(raw_text, str):
        return fallback_query, {}

    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except (ValueError, TypeError):
        logger.warning("Respuesta de extracción de filtros no es JSON válido; se continúa sin filtros.")
        return fallback_query, {}

    if not isinstance(parsed, dict):
        return fallback_query, {}

    search_text = parsed.get('search_text')
    if not isinstance(search_text, str) or not search_text.strip():
        search_text = fallback_query
    else:
        search_text = search_text.strip()

    filters = sanitize_filters(parsed)
    return search_text, filters


def format_catalog_product(product: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza la estructura de salida de un producto con los campos reales del catálogo de Django."""
    raw_cat = product.get('category')
    if isinstance(raw_cat, dict):
        category = {
            'id': raw_cat.get('id'),
            'name': raw_cat.get('name', ''),
            'description': raw_cat.get('description', ''),
        }
    else:
        category = {'id': None, 'name': str(raw_cat or ''), 'description': ''}

    return {
        'id': product.get('id'),
        'name': product.get('name', ''),
        'description': product.get('description', ''),
        'price': str(product.get('price', '0.00')),
        'stock': int(product.get('stock', 0)),
        'color': product.get('color', ''),
        'material': product.get('material', ''),
        'gender': product.get('gender', ''),
        'available_sizes': list(product.get('available_sizes') or []),
        'style': product.get('style', ''),
        'category': category,
    }


class ChatService:
    """Orquestador conversacional RAG del chatbot de Volt."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        search_service: SearchService,
        text_generator: TextGenerator,
        history_limit: int = 6,
    ):
        self.conversation_repo = conversation_repo
        self.search_service = search_service
        self.text_generator = text_generator
        self.history_limit = history_limit

    def _build_extraction_prompt(self, history: List[Dict[str, Any]], user_message: str) -> str:
        lines = ["Historial reciente:"]
        if not history:
            lines.append("(Sin mensajes previos)")
        else:
            for msg in history:
                role_label = "Usuario" if msg['role'] == 'user' else "Asesor"
                lines.append(f"- {role_label}: {msg['content']}")
        lines.append(f"\nMensaje actual del usuario: {user_message}")
        lines.append("\nDevuelve el JSON de intención y filtros:")
        return "\n".join(lines)

    def _build_rag_prompt(
        self,
        history: List[Dict[str, Any]],
        user_message: str,
        search_result: Dict[str, Any],
    ) -> str:
        lines = ["=== HISTORIAL RECIENTE ==="]
        if not history:
            lines.append("(Nueva conversación)")
        else:
            for msg in history:
                role_label = "Usuario" if msg['role'] == 'user' else "Asesor"
                lines.append(f"{role_label}: {msg['content']}")

        lines.append(f"\n=== CONSULTA ACTUAL DEL USUARIO ===\n{user_message}")

        applied_filters = search_result.get('applied_filters') or {}
        if applied_filters:
            serializable_filters = {k: str(v) for k, v in applied_filters.items()}
            lines.append(f"\n=== FILTROS APLICADOS ===\n{json.dumps(serializable_filters, ensure_ascii=False)}")

        products = search_result.get('products') or []
        out_of_stock = search_result.get('out_of_stock') or []

        lines.append("\n=== PRODUCTOS DISPONIBLES DEL CATÁLOGO (FUENTE DE VERDAD) ===")
        if products:
            for p in products:
                cat_name = (p.get('category') or {}).get('name', '') if isinstance(p.get('category'), dict) else ''
                sizes = ", ".join(p.get('available_sizes') or [])
                lines.append(
                    f"- [ID {p.get('id')}] {p.get('name')} | Categoría: {cat_name} | "
                    f"Precio: ${p.get('price')} COP | Stock: {p.get('stock')} | "
                    f"Color: {p.get('color', '')} | Material: {p.get('material', '')} | "
                    f"Género: {p.get('gender', '')} | Estilo: {p.get('style', '')} | "
                    f"Tallas: {sizes} | Descripción: {p.get('description', '')}"
                )
        else:
            lines.append("(Ningún producto disponible cumple los criterios y el umbral de relevancia)")

        if out_of_stock:
            lines.append("\n=== PRODUCTOS RELEVANTES PERO AGOTADOS (STOCK 0) ===")
            for p in out_of_stock:
                lines.append(f"- [ID {p.get('id')}] {p.get('name')} (AGOTADO - stock: 0)")

        lines.append(
            "\nRedacta la respuesta para el usuario respetando estrictamente los datos del catálogo anterior:"
        )
        return "\n".join(lines)

    def handle_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Procesa un turno de conversación: historial -> filtros -> búsqueda -> respuesta -> guardado."""
        clean_message = message.strip()

        if conversation_id is not None and str(conversation_id).strip() != '':
            conv = self.conversation_repo.get_conversation(str(conversation_id).strip())
            if conv is None:
                raise ConversationNotFoundError(f"La conversación '{conversation_id}' no existe.")
        else:
            conv = self.conversation_repo.create_conversation()

        history = self.conversation_repo.get_recent_messages(conv['id'], limit=self.history_limit)

        # Paso 1: Extraer intención y filtros en JSON (si el JSON es inválido, continúa sin filtros)
        extraction_prompt = self._build_extraction_prompt(history, clean_message)
        raw_extraction = self.text_generator.generate(
            prompt=extraction_prompt,
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
        )
        search_text, filters = parse_extraction_json(raw_extraction, fallback_query=clean_message)

        # Paso 2: Búsqueda híbrida determinista (embeddings + datos frescos de Django + filtros estrictos)
        search_result = self.search_service.search(query_text=search_text, filters=filters)

        # Paso 3: Construir prompt solo con los productos recuperados y generar respuesta
        rag_prompt = self._build_rag_prompt(history, clean_message, search_result)
        reply = self.text_generator.generate(
            prompt=rag_prompt,
            system_instruction=ADVISOR_SYSTEM_PROMPT,
        ).strip()

        if not reply:
            if search_result.get('products'):
                reply = "Aquí tienes las prendas del catálogo que mejor se ajustan a tu búsqueda."
            else:
                reply = (
                    "No encontré prendas disponibles en el catálogo que coincidan con tu búsqueda. "
                    "¿Podrías darme más detalles o ajustar tus filtros?"
                )

        # Paso 4: Guardar mensajes en la conversación
        self.conversation_repo.add_message(conv['id'], 'user', clean_message)
        self.conversation_repo.add_message(conv['id'], 'assistant', reply)

        formatted_products = [format_catalog_product(p) for p in (search_result.get('products') or [])]

        return {
            'conversation_id': conv['session_id'],
            'session_id': conv['session_id'],
            'reply': reply,
            'products': formatted_products,
        }
