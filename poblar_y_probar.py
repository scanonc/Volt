"""
Script de utilidad para poblar la base de datos de Volt y probar el Chatbot.

Acciones que realiza:
1. Carga las variables de entorno desde .env (GEMINI_API_KEY).
2. Inicializa Django y asegura los 12 productos demo en la base de datos de Django.
3. Inicializa la base de datos SQLite propia del microservicio de chatbot (chatbot_service/chatbot.sqlite3).
4. Genera embeddings semánticos con Google Gemini (gemini-embedding-001, 768 dims) e indexa el catálogo.
5. Ejecuta una prueba automática de recomendación con Gemini 3.8 Flash.
6. Inicia una sesión de chat interactiva en la terminal para que pruebes el asesor virtual en vivo.

Uso:
    python poblar_y_probar.py
    python poblar_y_probar.py --solo-poblar
"""

import os
import sys
from pathlib import Path
from decimal import Decimal

# 1. Asegurar paths y entorno
BASE_DIR = Path(__file__).resolve().parent
CHATBOT_DIR = BASE_DIR / 'chatbot_service'
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(CHATBOT_DIR))

# Cargar .env si existe python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

# Verificar API Key de Gemini
GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
if not GEMINI_KEY:
    print("=" * 70)
    print("❌ ERROR: No se encontró GEMINI_API_KEY en las variables de entorno ni en .env")
    print("Por favor, coloca tu clave en el archivo .env de la raíz:")
    print("    GEMINI_API_KEY=tu_clave_aqui")
    print("=" * 70)
    sys.exit(1)

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.core.management import call_command
from Volt.models import Product, Category
from Volt.serializers import ProductSerializer

# Importar componentes del microservicio chatbot
from app.config import Config
from app.db.sqlite import init_db
from app.db.repositories import ProductRepository, ConversationRepository
from app.providers.gemini import GeminiEmbeddingAdapter, GeminiTextAdapter
from app.services.indexer import IndexerService
from app.services.search import SearchService
from app.services.chat import ChatService


class DirectDjangoCatalogClient:
    """Cliente de catálogo directo que consulta el ORM de Django usando los mismos serializers."""

    def get_product(self, product_id: int):
        try:
            prod = Product.objects.get(id=product_id)
            return ProductSerializer(prod).data
        except Product.DoesNotExist:
            return None

    def get_products_by_ids(self, product_ids):
        if not product_ids:
            return []
        prods = Product.objects.filter(id__in=product_ids).order_by('id')
        return ProductSerializer(prods, many=True).data

    def list_products(self, limit: int = 50, offset: int = 0):
        prods = Product.objects.all().order_by('id')[offset:offset + limit]
        return ProductSerializer(prods, many=True).data


def asegurar_catalogo_django():
    """Verifica y carga los 12 productos demo en Django."""
    print("\n" + "=" * 70)
    print("📦 PASO 1: Verificando catálogo en Django...")
    print("=" * 70)
    
    total = Product.objects.count()
    if total < 12:
        print(f"Catálogo actual tiene {total} productos. Ejecutando 'cargar_demo'...")
        call_command('cargar_demo')
        total = Product.objects.count()
    
    print(f"✅ Catálogo de Django listo: {total} productos registrados.")
    for prod in Product.objects.all().order_by('id')[:5]:
        print(f"   - [ID {prod.id}] {prod.name} | ${prod.price:,.0f} COP | Stock: {prod.stock} | {prod.color} | {prod.style}")
    if total > 5:
        print(f"   ... y {total - 5} productos más.")


def indexar_chatbot():
    """Inicializa la base de datos SQLite del chatbot y genera los embeddings con Gemini."""
    print("\n" + "=" * 70)
    print("🧠 PASO 2: Inicializando e indexando base de datos SQLite del Chatbot...")
    print("=" * 70)

    db_path = Config.CHATBOT_DB_PATH
    print(f"Archivo SQLite del chatbot: {db_path}")
    init_db(db_path)

    product_repo = ProductRepository(db_path)
    catalog_client = DirectDjangoCatalogClient()
    
    print("Conectando con Google Gemini API (gemini-embedding-001, dim=768)...")
    embedding_provider = GeminiEmbeddingAdapter(
        api_key=GEMINI_KEY,
        model=Config.GEMINI_EMBEDDING_MODEL,
        dim=Config.EMBEDDING_DIM,
    )

    indexer = IndexerService(
        product_repo=product_repo,
        catalog_client=catalog_client,
        embedding_provider=embedding_provider,
        embedding_model=Config.GEMINI_EMBEDDING_MODEL,
        embedding_dim=Config.EMBEDDING_DIM,
    )

    print("Indexando productos en SQLite con control de hash SHA-256...")
    res = indexer.reindex_catalog(page_size=50)

    print(f"✅ Proceso de indexación completado:")
    print(f"   - Productos indexados/actualizados: {res['indexed']}")
    print(f"   - Productos sin cambios (cache hash): {res['unchanged']}")
    print(f"   - Productos eliminados (obsoletos): {res['deleted']}")
    print(f"   - Total en catálogo: {res['total_seen']}")

    total_indexed = len(product_repo.get_all_product_ids())
    print(f"✅ Total de vectores en SQLite chatbot: {total_indexed}")
    return product_repo, catalog_client, embedding_provider


def construir_chat_service(product_repo, catalog_client, embedding_provider):
    """Construye el ChatService completo con adaptadores reales."""
    db_path = Config.CHATBOT_DB_PATH
    conv_repo = ConversationRepository(db_path)

    search_service = SearchService(
        product_repo=product_repo,
        catalog_client=catalog_client,
        embedding_provider=embedding_provider,
        similarity_threshold=Config.SIMILARITY_THRESHOLD,
        top_k=Config.TOP_K,
        max_results=Config.MAX_RESULTS,
        embedding_dim=Config.EMBEDDING_DIM,
    )

    text_generator = GeminiTextAdapter(
        api_key=GEMINI_KEY,
        model=Config.GEMINI_TEXT_MODEL,
    )

    chat_service = ChatService(
        conversation_repo=conv_repo,
        search_service=search_service,
        text_generator=text_generator,
        history_limit=Config.HISTORY_LIMIT,
    )
    return chat_service


def ejecutar_prueba_automatica(chat_service):
    """Ejecuta una consulta de prueba automática para verificar el pipeline RAG completo."""
    print("\n" + "=" * 70)
    print("🤖 PASO 3: Prueba automática del asesor virtual (RAG con Gemini 3.8 Flash)...")
    print("=" * 70)

    pregunta_demo = "Hola, busco una camiseta negra deportiva para hombre"
    print(f"Consulta de prueba: \"{pregunta_demo}\"\n")
    print("Consultando asesor de Volt...")

    response = chat_service.handle_message(message=pregunta_demo)

    print("\n--- RESPUESTA DEL ASESOR ---")
    print(response['reply'])
    print("\n--- PRENDAS RECOMENDADAS ADJUNTAS ---")
    if response['products']:
        for p in response['products']:
            print(f"  • {p['name']} (${p['price']} COP) - Color: {p['color']}, Tallas: {', '.join(p['available_sizes'])}, Stock: {p['stock']}")
    else:
        print("  (Ninguna prenda directa)")
    print(f"\nID de Conversación creada: {response['conversation_id']}")
    print("=" * 70)


def iniciar_chat_interactivo(chat_service):
    """Inicia un ciclo interactivo en consola para conversar con el chatbot."""
    print("\n" + "=" * 70)
    print("💬 PASO 4: CHAT INTERACTIVO CON EL ASESOR VIRTUAL DE VOLT")
    print("Escribe tus consultas de moda, presupuesto o estilo.")
    print("Escribe 'salir' o 'exit' para terminar la sesión.")
    print("=" * 70)

    conversation_id = None

    while True:
        try:
            user_input = input("\nTú > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ('salir', 'exit', 'quit', 'q'):
                print("\n¡Gracias por consultar con Volt! Hasta pronto.\n")
                break

            print("\nAsesor Volt pensando...")
            resp = chat_service.handle_message(
                message=user_input,
                conversation_id=conversation_id,
            )
            conversation_id = resp['conversation_id']

            print(f"\nAsesor Volt >\n{resp['reply']}")
            if resp['products']:
                print("\n[Prendas recomendadas del catálogo:]")
                for p in resp['products']:
                    print(f"  * {p['name']} | ${p['price']} COP | Tallas: {', '.join(p['available_sizes'])} | Stock: {p['stock']}")

        except (KeyboardInterrupt, EOFError):
            print("\n\nSesión finalizada.")
            break
        except Exception as e:
            print(f"\n❌ Error al procesar mensaje: {e}")


def main():
    asegurar_catalogo_django()
    product_repo, catalog_client, embedding_provider = indexar_chatbot()
    chat_service = construir_chat_service(product_repo, catalog_client, embedding_provider)
    ejecutar_prueba_automatica(chat_service)

    if '--solo-poblar' not in sys.argv:
        iniciar_chat_interactivo(chat_service)


if __name__ == '__main__':
    main()
