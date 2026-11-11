"""Servicio independiente: no importa Django ni consulta su base de datos."""
from gettext import translation
from pathlib import Path

import hmac
import logging
import os

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


english = translation('messages', Path(__file__).parent / 'locale', languages=['en'])


def _(message):
    if request.accept_languages.best_match(['es', 'en']) == 'en':
        return english.gettext(message)
    return message


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(NOTIFICATIONS_API_KEY=os.environ.get('NOTIFICATIONS_API_KEY', ''),
                      MAX_CONTENT_LENGTH=16384)
    if config:
        app.config.update(config)

    @app.get('/health/')
    def health():
        return jsonify(status='ok', service='notifications')

    @app.post('/api/v2/notifications/')
    def confirmation():
        key = app.config['NOTIFICATIONS_API_KEY']
        if not key:
            return jsonify(error={'code': 'not_configured', 'message': _('Servicio sin configurar.')}), 503
        if not hmac.compare_digest(request.headers.get('X-API-Key', ''), key):
            return jsonify(error={'code': 'unauthorized', 'message': _('Credenciales inválidas.')}), 401
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error={'code': 'invalid_json', 'message': _('Se requiere un objeto JSON.')}), 400
        order_id, username = data.get('order_id'), data.get('username')
        channel = data.get('channel', 'console')
        if (type(order_id) is not int or order_id <= 0 or
                not isinstance(username, str) or not username.strip() or len(username) > 150 or
                channel not in ('console', 'email')):
            return jsonify(error={'code': 'invalid_payload', 'message':
                _('order_id debe ser entero positivo, username texto de 1 a 150 caracteres y channel console o email.')}), 400
        # Se conserva el alcance original: ambos canales son simulados.
        message = (_('Pedido #%(order_id)s confirmado para %(username)s') if channel == 'console'
                   else _('Correo de confirmación enviado para pedido #%(order_id)s'))
        app.logger.info('notification order_id=%s channel=%s', order_id, channel)
        return jsonify(order_id=order_id, channel=channel, status='simulated', message=message % {'order_id': order_id, 'username': username}), 200

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error={'code': 'http_error', 'message': exc.description}), exc.code

    @app.errorhandler(Exception)
    def server_error(exc):
        app.logger.exception('Error procesando notificación')
        return jsonify(error={'code': 'internal_error', 'message': _('No se pudo procesar la notificación.')}), 500

    return app


logging.basicConfig(level=logging.INFO)
app = create_app()
