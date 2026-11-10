import logging
import socket
from typing import Any, List, Optional
import numpy as np

from google import genai
from google.genai import errors, types

from .base import (
    EmbeddingProvider,
    ProviderAuthError,
    ProviderError,
    ProviderQuotaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TextGenerator,
)

logger = logging.getLogger(__name__)


def _map_gemini_error(exc: Exception) -> ProviderError:
    """Traduce excepciones del SDK google-genai a excepciones propias del dominio."""
    if isinstance(exc, ProviderError):
        return exc

    code = getattr(exc, 'code', None)
    err_str = str(exc).lower()

    # Timeouts
    if isinstance(exc, (TimeoutError, socket.timeout)) or code in (408, 504) or 'timed out' in err_str:
        return ProviderTimeoutError(f"Tiempo de espera agotado con Gemini: {exc}")

    # Autenticación / Permisos
    if code in (401, 403) or 'api key' in err_str or 'unauthorized' in err_str or 'permission_denied' in err_str:
        return ProviderAuthError(f"Error de autenticación o permisos con Gemini: {exc}")

    # Cuota / Rate limit
    if code == 429 or 'quota' in err_str or 'resource_exhausted' in err_str:
        return ProviderQuotaError(f"Cuota o límite de peticiones excedido en Gemini: {exc}")

    # Indisponibilidad / Errores 5xx
    if code in (500, 502, 503) or 'unavailable' in err_str or 'server error' in err_str:
        return ProviderUnavailableError(f"Servicio Gemini temporalmente no disponible: {exc}")

    return ProviderError(f"Fallo en comunicación con Gemini: {exc}")


class GeminiEmbeddingAdapter(EmbeddingProvider):
    """Adaptador para el modelo de embeddings de Gemini (gemini-embedding-001)."""

    def __init__(
        self,
        api_key: str = '',
        model: str = 'gemini-embedding-001',
        dim: int = 768,
        client: Optional[genai.Client] = None,
    ):
        self.model = model
        self.dim = dim
        if client is not None:
            self.client = client
        elif api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    def _embed(self, text: str, task_type: str) -> List[float]:
        if not self.client:
            raise ProviderAuthError("GEMINI_API_KEY no configurada para el adaptador de embeddings.")

        if not text or not text.strip():
            raise ProviderError("El texto a embeber no puede estar vacío.")

        try:
            config = types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dim,
            )
            response = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=config,
            )
        except Exception as exc:
            logger.error("Error al llamar a Gemini embed_content: %s", exc)
            raise _map_gemini_error(exc) from exc

        if not response or not getattr(response, 'embeddings', None) or not response.embeddings:
            raise ProviderError("Gemini retornó una respuesta de embedding vacía.")

        values = getattr(response.embeddings[0], 'values', None)
        if not values:
            raise ProviderError("Valores de embedding vacíos en la respuesta de Gemini.")

        if len(values) != self.dim:
            logger.warning(
                "Dimensión devuelta por Gemini (%d) difiere de la esperada (%d).",
                len(values),
                self.dim,
            )

        # Normalización manual L2
        vec = np.array(values, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            raise ProviderError("Norma vectorial nula en el embedding generado.")

        return vec.tolist()

    def embed_document(self, text: str) -> List[float]:
        """Genera embedding para indexación de documento/producto (RETRIEVAL_DOCUMENT)."""
        return self._embed(text, task_type='RETRIEVAL_DOCUMENT')

    def embed_query(self, text: str) -> List[float]:
        """Genera embedding para búsqueda/consulta (RETRIEVAL_QUERY)."""
        return self._embed(text, task_type='RETRIEVAL_QUERY')


class GeminiTextAdapter(TextGenerator):
    """Adaptador para el modelo generativo de Gemini (gemini-3.8-flash)."""

    def __init__(
        self,
        api_key: str = '',
        model: str = 'gemini-3.8-flash',
        client: Optional[genai.Client] = None,
    ):
        self.model = model
        if client is not None:
            self.client = client
        elif api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.client:
            raise ProviderAuthError("GEMINI_API_KEY no configurada para el adaptador de texto.")

        if not prompt or not prompt.strip():
            raise ProviderError("El prompt para generar texto no puede estar vacío.")

        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(system_instruction=system_instruction)

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            logger.error("Error al llamar a Gemini generate_content: %s", exc)
            raise _map_gemini_error(exc) from exc

        text = getattr(response, 'text', None)
        if text is None:
            return ""
        return str(text)
