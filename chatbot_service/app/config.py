import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Configuración base para el microservicio chatbot."""

    # Gemini (NO obligatoria para tests ni arranque inicial)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    GEMINI_EMBEDDING_MODEL = os.environ.get('GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001')
    GEMINI_TEXT_MODEL = os.environ.get('GEMINI_TEXT_MODEL', 'gemini-3.8-flash')
    EMBEDDING_DIM = int(os.environ.get('EMBEDDING_DIM', '768'))

    # Base de datos SQLite
    CHATBOT_DB_PATH = os.environ.get('CHATBOT_DB_PATH', str(BASE_DIR / 'chatbot.sqlite3'))

    # Comunicación con Django
    DJANGO_BASE_URL = os.environ.get('DJANGO_BASE_URL', 'http://django:8000').rstrip('/')
    DJANGO_TIMEOUT = float(os.environ.get('DJANGO_TIMEOUT', '2.0'))
    INTERNAL_API_KEY = os.environ.get('INTERNAL_API_KEY', '')

    # Búsqueda y ranking
    SIMILARITY_THRESHOLD = float(os.environ.get('SIMILARITY_THRESHOLD', '0.55'))
    TOP_K = int(os.environ.get('TOP_K', '10'))
    MAX_RESULTS = int(os.environ.get('MAX_RESULTS', '4'))
    MAX_MESSAGE_LENGTH = int(os.environ.get('MAX_MESSAGE_LENGTH', '1000'))
    HISTORY_LIMIT = int(os.environ.get('HISTORY_LIMIT', '6'))

    # Celery / Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    TESTING = False
