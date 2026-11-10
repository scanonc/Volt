import os
from pathlib import Path
import tempfile
import unittest

from app.db.sqlite import init_db
from app.db.repositories import ProductRepository, ConversationRepository


class RepositoriesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test_chatbot.sqlite3')
        init_db(self.db_path)
        self.product_repo = ProductRepository(self.db_path)
        self.conv_repo = ConversationRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- ProductRepository tests ---

    def test_upsert_and_get_product(self):
        sample_embedding = [0.1, 0.2, 0.3, 0.4]
        self.product_repo.upsert(
            product_id=42,
            content_hash="abc123hash",
            embedding=sample_embedding,
            model="gemini-embedding-001",
            dim=4,
        )

        item = self.product_repo.get(42)
        self.assertIsNotNone(item)
        self.assertEqual(item['product_id'], 42)
        self.assertEqual(item['content_hash'], "abc123hash")
        self.assertEqual(item['embedding'], sample_embedding)
        self.assertEqual(item['embedding_model'], "gemini-embedding-001")
        self.assertEqual(item['embedding_dim'], 4)
        self.assertIsNotNone(item['updated_at'])

    def test_upsert_updates_existing_product(self):
        self.product_repo.upsert(
            product_id=1,
            content_hash="hash_v1",
            embedding=[0.5, 0.5],
            model="gemini-embedding-001",
            dim=2,
        )
        self.assertEqual(self.product_repo.get_hash(1), "hash_v1")

        # Actualizar con nuevo hash y vector
        self.product_repo.upsert(
            product_id=1,
            content_hash="hash_v2",
            embedding=[0.8, 0.6],
            model="gemini-embedding-001",
            dim=2,
        )
        item = self.product_repo.get(1)
        self.assertEqual(item['content_hash'], "hash_v2")
        self.assertEqual(item['embedding'], [0.8, 0.6])
        self.assertEqual(self.product_repo.count(), 1)

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.product_repo.get(999))
        self.assertIsNone(self.product_repo.get_hash(999))

    def test_delete_product(self):
        self.product_repo.upsert(10, "h10", [0.1], "m", 1)
        self.assertTrue(self.product_repo.delete(10))
        self.assertIsNone(self.product_repo.get(10))
        # Borrar de nuevo retorna False
        self.assertFalse(self.product_repo.delete(10))

    def test_get_all_embeddings_and_product_ids(self):
        self.product_repo.upsert(1, "h1", [1.0, 0.0], "m", 2)
        self.product_repo.upsert(2, "h2", [0.0, 1.0], "m", 2)
        self.product_repo.upsert(3, "h3", [0.7, 0.7], "m", 2)

        embeddings = self.product_repo.get_all_embeddings()
        self.assertEqual(len(embeddings), 3)

        ids = self.product_repo.get_all_product_ids()
        self.assertEqual(ids, {1, 2, 3})
        self.assertEqual(self.product_repo.count(), 3)

    # --- ConversationRepository tests ---

    def test_get_or_create_conversation(self):
        c1 = self.conv_repo.get_or_create_conversation("session-xyz")
        self.assertIsNotNone(c1['id'])
        self.assertEqual(c1['session_id'], "session-xyz")

        # Segunda llamada retorna la misma conversación
        c2 = self.conv_repo.get_or_create_conversation("session-xyz")
        self.assertEqual(c1['id'], c2['id'])

    def test_add_message_and_get_recent_messages(self):
        conv = self.conv_repo.get_or_create_conversation("session-abc")
        conv_id = conv['id']

        # Añadir 8 mensajes
        for i in range(1, 9):
            role = 'user' if i % 2 == 1 else 'assistant'
            self.conv_repo.add_message(conv_id, role, f"Mensaje {i}")

        # Pedir los últimos 4 mensajes
        recent = self.conv_repo.get_recent_messages(conv_id, limit=4)
        self.assertEqual(len(recent), 4)

        # Deben venir en orden cronológico (5, 6, 7, 8)
        contents = [m['content'] for m in recent]
        self.assertEqual(contents, ["Mensaje 5", "Mensaje 6", "Mensaje 7", "Mensaje 8"])
        self.assertEqual([m['role'] for m in recent], ['user', 'assistant', 'user', 'assistant'])


if __name__ == '__main__':
    unittest.main()
