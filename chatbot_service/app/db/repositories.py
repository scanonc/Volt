import json
import sqlite3
from typing import Any, Dict, List, Optional, Set
import uuid

from .sqlite import get_db_connection


class ProductRepository:
    """Repositorio para almacenamiento y consulta de embeddings de productos en SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def upsert(
        self,
        product_id: int,
        content_hash: str,
        embedding: List[float],
        model: str,
        dim: int,
    ) -> None:
        """Inserta o actualiza el vector y metadatos de un producto."""
        embedding_json = json.dumps(embedding)
        sql = """
        INSERT INTO indexed_products (product_id, content_hash, embedding, embedding_model, embedding_dim, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(product_id) DO UPDATE SET
            content_hash = excluded.content_hash,
            embedding = excluded.embedding,
            embedding_model = excluded.embedding_model,
            embedding_dim = excluded.embedding_dim,
            updated_at = CURRENT_TIMESTAMP;
        """
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(sql, (product_id, content_hash, embedding_json, model, dim))
        finally:
            conn.close()

    def get(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene un producto indexado con su embedding deserializado."""
        sql = """
        SELECT product_id, content_hash, embedding, embedding_model, embedding_dim, updated_at
        FROM indexed_products
        WHERE product_id = ?;
        """
        conn = self._get_conn()
        try:
            row = conn.execute(sql, (product_id,)).fetchone()
            if row is None:
                return None
            return {
                'product_id': row['product_id'],
                'content_hash': row['content_hash'],
                'embedding': json.loads(row['embedding']),
                'embedding_model': row['embedding_model'],
                'embedding_dim': row['embedding_dim'],
                'updated_at': row['updated_at'],
            }
        finally:
            conn.close()

    def get_hash(self, product_id: int) -> Optional[str]:
        """Obtiene únicamente el hash actual para verificar si requiere re-indexar."""
        sql = "SELECT content_hash FROM indexed_products WHERE product_id = ?;"
        conn = self._get_conn()
        try:
            row = conn.execute(sql, (product_id,)).fetchone()
            return row['content_hash'] if row else None
        finally:
            conn.close()

    def delete(self, product_id: int) -> bool:
        """Elimina un producto del índice."""
        sql = "DELETE FROM indexed_products WHERE product_id = ?;"
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute(sql, (product_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def get_all_embeddings(self) -> List[Dict[str, Any]]:
        """Retorna todos los embeddings indexados para cálculo de similitud."""
        sql = """
        SELECT product_id, content_hash, embedding, embedding_model, embedding_dim, updated_at
        FROM indexed_products;
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(sql).fetchall()
            results = []
            for row in rows:
                results.append({
                    'product_id': row['product_id'],
                    'content_hash': row['content_hash'],
                    'embedding': json.loads(row['embedding']),
                    'embedding_model': row['embedding_model'],
                    'embedding_dim': row['embedding_dim'],
                    'updated_at': row['updated_at'],
                })
            return results
        finally:
            conn.close()

    def get_all_product_ids(self) -> Set[int]:
        """Retorna el conjunto de IDs presentes en el índice para reconciliación."""
        sql = "SELECT product_id FROM indexed_products;"
        conn = self._get_conn()
        try:
            rows = conn.execute(sql).fetchall()
            return {row['product_id'] for row in rows}
        finally:
            conn.close()

    def count(self) -> int:
        """Cantidad total de productos indexados."""
        sql = "SELECT COUNT(*) as cnt FROM indexed_products;"
        conn = self._get_conn()
        try:
            row = conn.execute(sql).fetchone()
            return row['cnt'] if row else 0
        finally:
            conn.close()


class ConversationRepository:
    """Repositorio para conversaciones y mensajes del chatbot en SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def create_conversation(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Crea una nueva conversación generando un UUID si no se especifica session_id."""
        sid = session_id or uuid.uuid4().hex
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO conversations (session_id) VALUES (?);",
                    (sid,),
                )
                conv_id = cursor.lastrowid
                row = conn.execute(
                    "SELECT id, session_id, created_at FROM conversations WHERE id = ?;",
                    (conv_id,),
                ).fetchone()
                return {'id': row['id'], 'session_id': row['session_id'], 'created_at': row['created_at']}
        finally:
            conn.close()

    def get_or_create_conversation(self, session_id: str) -> Dict[str, Any]:
        """Busca o crea una conversación por su session_id."""
        existing = self.get_conversation(session_id)
        if existing is not None:
            return existing
        return self.create_conversation(session_id=session_id)

    def get_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene una conversación por session_id (o por id numérico si aplica)."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT id, session_id, created_at FROM conversations WHERE session_id = ?;",
                (str(session_id),),
            ).fetchone()
            if row is None and str(session_id).isdigit():
                row = conn.execute(
                    "SELECT id, session_id, created_at FROM conversations WHERE id = ?;",
                    (int(session_id),),
                ).fetchone()
            if row is None:
                return None
            return {'id': row['id'], 'session_id': row['session_id'], 'created_at': row['created_at']}
        finally:
            conn.close()

    def add_message(self, conversation_id: int, role: str, content: str) -> Dict[str, Any]:
        """Agrega un mensaje a la conversación."""
        sql = """
        INSERT INTO messages (conversation_id, role, content)
        VALUES (?, ?, ?);
        """
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute(sql, (conversation_id, role, content))
                msg_id = cursor.lastrowid
                row = conn.execute(
                    "SELECT id, conversation_id, role, content, created_at FROM messages WHERE id = ?;",
                    (msg_id,),
                ).fetchone()
                return {
                    'id': row['id'],
                    'conversation_id': row['conversation_id'],
                    'role': row['role'],
                    'content': row['content'],
                    'created_at': row['created_at'],
                }
        finally:
            conn.close()

    def get_recent_messages(self, conversation_id: int, limit: int = 6) -> List[Dict[str, Any]]:
        """Obtiene los últimos N mensajes ordenados cronológicamente."""
        sql = """
        SELECT id, conversation_id, role, content, created_at
        FROM (
            SELECT id, conversation_id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id ASC;
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, (conversation_id, limit)).fetchall()
            return [
                {
                    'id': row['id'],
                    'conversation_id': row['conversation_id'],
                    'role': row['role'],
                    'content': row['content'],
                    'created_at': row['created_at'],
                }
                for row in rows
            ]
        finally:
            conn.close()
