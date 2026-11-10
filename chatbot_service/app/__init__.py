import logging
import click
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .api.internal import internal_bp
from .api.public import public_bp
from .config import Config
from .db.sqlite import init_db
from .tasks.indexing import build_default_indexer

logger = logging.getLogger(__name__)


def create_app(test_config=None) -> Flask:
    """Application factory para el microservicio chatbot."""
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # Configuración de logging básico si no está configurado
    if not app.logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        )

    # Inicialización de esquema SQLite si está configurado
    db_path = app.config.get('CHATBOT_DB_PATH')
    if db_path and app.config.get('INIT_DB_ON_STARTUP', True):
        try:
            init_db(db_path)
            app.logger.info("Base de datos SQLite inicializada en: %s", db_path)
        except Exception as exc:
            app.logger.error("No se pudo inicializar la base de datos SQLite: %s", exc)

    # Registro de Blueprints
    app.register_blueprint(public_bp)
    app.register_blueprint(internal_bp)

    # Comando CLI para reindexación inicial/manual
    @app.cli.command("reindex")
    def reindex_command():
        """Ejecuta la reindexación completa del catálogo desde Django."""
        indexer = build_default_indexer()
        summary = indexer.reindex_catalog()
        click.echo(
            f"Reindexación completada: {summary['indexed']} indexados, "
            f"{summary['unchanged']} sin cambios, {summary['deleted']} eliminados."
        )

    # Manejadores globales de errores (JSON limpio sin detalles internos)
    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return jsonify(error={
            'code': 'http_error',
            'message': exc.description,
        }), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected_exception(exc: Exception):
        app.logger.exception("Error no controlado en microservicio chatbot: %s", exc)
        return jsonify(error={
            'code': 'internal_error',
            'message': 'Ocurrió un error interno en el servicio de chatbot.',
        }), 500

    return app
