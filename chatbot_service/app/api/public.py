from flask import Blueprint, jsonify

public_bp = Blueprint('public', __name__, url_prefix='/api/chatbot')


@public_bp.get('/health/')
def health():
    """Endpoint de salud del microservicio chatbot."""
    return jsonify(status='ok', service='chatbot'), 200
