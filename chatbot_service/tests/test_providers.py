from unittest.mock import MagicMock
import unittest
import numpy as np

from google.genai import errors

from app.providers.base import (
    FakeEmbeddingProvider,
    FakeTextGenerator,
    ProviderAuthError,
    ProviderError,
    ProviderQuotaError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.gemini import GeminiEmbeddingAdapter, GeminiTextAdapter


class FakeProvidersTests(unittest.TestCase):
    def test_fake_embedding_provider_determinism_and_dimension(self):
        provider = FakeEmbeddingProvider(dim=768)
        v1 = provider.embed_document("Camiseta básica blanca")
        v2 = provider.embed_document("Camiseta básica blanca")
        v3 = provider.embed_document("Jean azul clásico")

        self.assertEqual(len(v1), 768)
        self.assertEqual(v1, v2)
        self.assertNotEqual(v1, v3)

    def test_fake_embedding_provider_l2_normalization(self):
        provider = FakeEmbeddingProvider(dim=128)
        vec = provider.embed_query("pantalón deportivo")
        norm = np.linalg.norm(np.array(vec, dtype=np.float32))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_fake_text_generator(self):
        gen = FakeTextGenerator(default_response="Default")
        self.assertEqual(gen.generate("Hola"), "Default")

        gen.queue_response("Respuesta encolada 1")
        gen.queue_response("Respuesta encolada 2")
        self.assertEqual(gen.generate("Test 1"), "Respuesta encolada 1")
        self.assertEqual(gen.generate("Test 2"), "Respuesta encolada 2")
        self.assertEqual(gen.generate("Test 3"), "Default")

        gen.set_response_for("clima", "Hace frío.")
        self.assertEqual(gen.generate("¿Cómo está el clima hoy?"), "Hace frío.")
        self.assertEqual(len(gen.calls), 5)


class GeminiEmbeddingAdapterTests(unittest.TestCase):
    def test_embed_document_calls_sdk_with_retrieval_document(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        # Vector no normalizado
        mock_embedding.values = [3.0, 4.0]
        mock_response.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_response

        adapter = GeminiEmbeddingAdapter(client=mock_client, model="gemini-embedding-001", dim=2)
        result = adapter.embed_document("Camisa de lino")

        mock_client.models.embed_content.assert_called_once()
        call_kwargs = mock_client.models.embed_content.call_args.kwargs
        self.assertEqual(call_kwargs['model'], "gemini-embedding-001")
        self.assertEqual(call_kwargs['contents'], "Camisa de lino")
        self.assertEqual(call_kwargs['config'].task_type, "RETRIEVAL_DOCUMENT")
        self.assertEqual(call_kwargs['config'].output_dimensionality, 2)

        # Verificar normalización manual L2: [3, 4] / 5 = [0.6, 0.8]
        self.assertAlmostEqual(result[0], 0.6, places=5)
        self.assertAlmostEqual(result[1], 0.8, places=5)
        norm = np.linalg.norm(result)
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_embed_query_calls_sdk_with_retrieval_query(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.values = [1.0, 0.0]
        mock_response.embeddings = [mock_embedding]
        mock_client.models.embed_content.return_value = mock_response

        adapter = GeminiEmbeddingAdapter(client=mock_client, dim=2)
        adapter.embed_query("busco algo fresco")

        call_kwargs = mock_client.models.embed_content.call_args.kwargs
        self.assertEqual(call_kwargs['config'].task_type, "RETRIEVAL_QUERY")

    def test_empty_text_raises_provider_error(self):
        adapter = GeminiEmbeddingAdapter(client=MagicMock())
        with self.assertRaises(ProviderError):
            adapter.embed_document("   ")

    def test_missing_client_and_key_raises_auth_error(self):
        adapter = GeminiEmbeddingAdapter(api_key='', client=None)
        with self.assertRaises(ProviderAuthError):
            adapter.embed_document("algo")

    def test_error_mapping_auth(self):
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = errors.APIError(401, {'error': {'message': 'Invalid API Key'}})
        adapter = GeminiEmbeddingAdapter(client=mock_client)

        with self.assertRaises(ProviderAuthError):
            adapter.embed_document("texto")

    def test_error_mapping_quota(self):
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = errors.APIError(429, {'error': {'message': 'Resource Exhausted'}})
        adapter = GeminiEmbeddingAdapter(client=mock_client)

        with self.assertRaises(ProviderQuotaError):
            adapter.embed_document("texto")

    def test_error_mapping_timeout(self):
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = TimeoutError("Request timed out")
        adapter = GeminiEmbeddingAdapter(client=mock_client)

        with self.assertRaises(ProviderTimeoutError):
            adapter.embed_document("texto")

    def test_error_mapping_unavailable(self):
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = errors.APIError(503, {'error': {'message': 'Service Unavailable'}})
        adapter = GeminiEmbeddingAdapter(client=mock_client)

        with self.assertRaises(ProviderUnavailableError):
            adapter.embed_document("texto")


class GeminiTextAdapterTests(unittest.TestCase):
    def test_generate_calls_generate_content_with_correct_parameters(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "¡Hola! Te recomiendo la camiseta blanca."
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiTextAdapter(client=mock_client, model="gemini-2.5-flash-lite")
        reply = adapter.generate(prompt="¿Qué me recomiendas?", system_instruction="Eres un asesor.")

        self.assertEqual(reply, "¡Hola! Te recomiendo la camiseta blanca.")
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs['model'], "gemini-2.5-flash-lite")
        self.assertEqual(call_kwargs['contents'], "¿Qué me recomiendas?")
        self.assertEqual(call_kwargs['config'].system_instruction, "Eres un asesor.")

    def test_generate_empty_prompt_raises_provider_error(self):
        adapter = GeminiTextAdapter(client=MagicMock())
        with self.assertRaises(ProviderError):
            adapter.generate("")

    def test_generate_error_mapping_quota(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = errors.APIError(429, {'error': {'message': 'Quota exceeded'}})
        adapter = GeminiTextAdapter(client=mock_client)

        with self.assertRaises(ProviderQuotaError):
            adapter.generate("Hola")


if __name__ == '__main__':
    unittest.main()
