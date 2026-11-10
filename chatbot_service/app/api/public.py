from flask import Blueprint, current_app, jsonify, request

from app.db.repositories import ConversationRepository, ProductRepository
from app.providers.base import ProviderError
from app.providers.gemini import GeminiEmbeddingAdapter, GeminiTextAdapter
from app.services.catalog_client import CatalogClient, CatalogClientError
from app.services.chat import ChatService, ConversationNotFoundError
from app.services.indexer import InvalidEmbeddingError
from app.services.search import SearchService

public_bp = Blueprint('public', __name__, url_prefix='/api/chatbot')


def _get_chat_service() -> ChatService:
    """Obtiene el servicio de chat inyectado en config o construye uno a partir de la configuración."""
    injected = current_app.config.get('CHAT_SERVICE')
    if injected is not None:
        return injected

    db_path = current_app.config['CHATBOT_DB_PATH']
    product_repo = current_app.config.get('PRODUCT_REPO') or ProductRepository(db_path)
    conv_repo = current_app.config.get('CONVERSATION_REPO') or ConversationRepository(db_path)

    catalog_client = current_app.config.get('CATALOG_CLIENT') or CatalogClient(
        base_url=current_app.config['DJANGO_BASE_URL'],
        timeout=current_app.config['DJANGO_TIMEOUT'],
    )

    embedding_provider = current_app.config.get('EMBEDDING_PROVIDER') or GeminiEmbeddingAdapter(
        api_key=current_app.config.get('GEMINI_API_KEY', ''),
        model=current_app.config.get('GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001'),
        dim=current_app.config.get('EMBEDDING_DIM', 768),
    )

    text_generator = current_app.config.get('TEXT_GENERATOR') or GeminiTextAdapter(
        api_key=current_app.config.get('GEMINI_API_KEY', ''),
        model=current_app.config.get('GEMINI_TEXT_MODEL', 'gemini-3.8-flash'),
    )

    search_service = current_app.config.get('SEARCH_SERVICE') or SearchService(
        product_repo=product_repo,
        catalog_client=catalog_client,
        embedding_provider=embedding_provider,
        similarity_threshold=current_app.config.get('SIMILARITY_THRESHOLD', 0.55),
        top_k=current_app.config.get('TOP_K', 10),
        max_results=current_app.config.get('MAX_RESULTS', 4),
        embedding_dim=current_app.config.get('EMBEDDING_DIM', 768),
    )

    return ChatService(
        conversation_repo=conv_repo,
        search_service=search_service,
        text_generator=text_generator,
        history_limit=current_app.config.get('HISTORY_LIMIT', 6),
    )


@public_bp.get('/health/')
def health():
    """Endpoint de salud del microservicio chatbot."""
    return jsonify(status='ok', service='chatbot'), 200


@public_bp.post('/message/', strict_slashes=False)
def message():
    """Endpoint público síncrono para enviar un mensaje al asesor virtual de Volt."""
    if not request.is_json:
        return jsonify(error={
            'code': 'invalid_json',
            'message': 'El cuerpo de la petición debe ser un objeto JSON válido.',
        }), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error={
            'code': 'invalid_json',
            'message': 'Se requiere un objeto JSON.',
        }), 400

    raw_message = data.get('message')
    max_len = int(current_app.config.get('MAX_MESSAGE_LENGTH', 1000))
    if not isinstance(raw_message, str) or not raw_message.strip():
        return jsonify(error={
            'code': 'invalid_payload',
            'message': 'El campo "message" es obligatorio y debe ser un texto no vacío.',
        }), 400

    if len(raw_message.strip()) > max_len:
        return jsonify(error={
            'code': 'invalid_payload',
            'message': f'El mensaje supera la longitud máxima permitida ({max_len} caracteres).',
        }), 400

    # Soportar conversation_id (o alias session_id) opcional
    conv_id = data.get('conversation_id')
    if conv_id is None and 'session_id' in data:
        conv_id = data.get('session_id')

    if conv_id is not None:
        if not isinstance(conv_id, str) or not conv_id.strip() or len(conv_id.strip()) > 128:
            return jsonify(error={
                'code': 'invalid_payload',
                'message': 'El campo "conversation_id" debe ser una cadena válida de hasta 128 caracteres.',
            }), 400
        conv_id = conv_id.strip()

    try:
        chat_service = _get_chat_service()
        result = chat_service.handle_message(message=raw_message, conversation_id=conv_id)
        return jsonify(result), 200
    except ConversationNotFoundError:
        return jsonify(error={
            'code': 'conversation_not_found',
            'message': 'La conversación indicada no existe.',
        }), 404
    except (ProviderError, InvalidEmbeddingError) as exc:
        current_app.logger.error("Error del proveedor de IA al procesar mensaje: %s", exc)
        return jsonify(error={
            'code': 'llm_unavailable',
            'message': 'El asistente virtual no está disponible temporalmente. Intenta de nuevo en unos momentos.',
        }), 503
    except CatalogClientError as exc:
        current_app.logger.error("Error al consultar el catálogo de Django: %s", exc)
        return jsonify(error={
            'code': 'catalog_unavailable',
            'message': 'No fue posible consultar el catálogo de productos en este momento.',
        }), 502
