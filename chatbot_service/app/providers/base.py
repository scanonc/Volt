from abc import ABC, abstractmethod
import hashlib
from typing import Any, Dict, List, Optional
import numpy as np


class ProviderError(Exception):
    """Excepción base para fallos en proveedores de IA."""
    pass


class ProviderAuthError(ProviderError):
    """Fallo de autenticación o clave API inválida."""
    pass


class ProviderQuotaError(ProviderError):
    """Límite de cuota o tasa de peticiones excedido."""
    pass


class ProviderTimeoutError(ProviderError):
    """Tiempo de espera agotado al comunicarse con el proveedor."""
    pass


class ProviderUnavailableError(ProviderError):
    """Servicio del proveedor caído o no disponible."""
    pass


class EmbeddingProvider(ABC):
    """Interfaz para generación de embeddings vectoriales."""

    @abstractmethod
    def embed_document(self, text: str) -> List[float]:
        """Genera embedding para indexación de documento/producto."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Genera embedding para consulta de usuario."""
        pass


class TextGenerator(ABC):
    """Interfaz para generación de texto / respuestas LLM."""

    @abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Genera texto a partir de un prompt e instrucción opcional."""
        pass


class FakeEmbeddingProvider(EmbeddingProvider):
    """Proveedor determinista de prueba para tests sin llamadas a API externa."""

    def __init__(self, dim: int = 768):
        self.dim = dim
        self.embedded_documents: List[str] = []
        self.embedded_queries: List[str] = []

    def _generate_vector(self, text: str, salt: str) -> List[float]:
        # Semilla determinista a partir de SHA-256
        seed_bytes = hashlib.sha256(f"{salt}:{text}".encode('utf-8')).digest()
        # Generar vector pseudoaleatorio determinista
        rng = np.random.RandomState(int.from_bytes(seed_bytes[:4], 'big'))
        vec = rng.randn(self.dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_document(self, text: str) -> List[float]:
        self.embedded_documents.append(text)
        return self._generate_vector(text, salt="doc")

    def embed_query(self, text: str) -> List[float]:
        self.embedded_queries.append(text)
        return self._generate_vector(text, salt="query")


class FakeTextGenerator(TextGenerator):
    """Generador de texto simulado para tests sin llamadas a API externa."""

    def __init__(self, default_response: str = "Respuesta simulada del asistente."):
        self.default_response = default_response
        self.responses_queue: List[str] = []
        self.canned_responses: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []

    def queue_response(self, text: str) -> None:
        self.responses_queue.append(text)

    def set_response_for(self, pattern: str, response: str) -> None:
        self.canned_responses[pattern] = response

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        self.calls.append({'prompt': prompt, 'system_instruction': system_instruction})

        if self.responses_queue:
            return self.responses_queue.pop(0)

        for pattern, resp in self.canned_responses.items():
            if pattern in prompt:
                return resp

        return self.default_response
