import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


class WrongQuestionDB:
    def __init__(self, db_path: str = "wrong_questions.db"):
        self.db_path = os.path.abspath(db_path)
        self._fallback_db_path = os.path.abspath(os.path.join(os.getcwd(), "wrong_questions_runtime.db"))
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, dict)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            with self._get_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wrong_questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question_text TEXT NOT NULL,
                        answer_text TEXT NOT NULL,
                        error_reason TEXT NOT NULL,
                        source_type TEXT DEFAULT 'image',
                        image_path TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()
        except sqlite3.OperationalError as exc:
            if "readonly" in str(exc).lower() and self.db_path != self._fallback_db_path:
                self.db_path = self._fallback_db_path
                self._init_db()
                return
            raise

    def _retry_with_fallback(self) -> None:
        if self.db_path != self._fallback_db_path:
            self.db_path = self._fallback_db_path
            self._init_db()

    def add_wrong_question(
        self,
        question_text: Any,
        answer_text: Any,
        error_reason: Any,
        source_type: str = "image",
        image_path: Optional[str] = None,
    ) -> int:
        question_text = self._to_text(question_text)
        answer_text = self._to_text(answer_text)
        error_reason = self._to_text(error_reason)
        image_path = self._to_text(image_path) if image_path is not None else None

        try:
            with self._get_conn() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO wrong_questions (
                        question_text, answer_text, error_reason, source_type, image_path
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (question_text, answer_text, error_reason, source_type, image_path),
                )
                conn.commit()
                return int(cur.lastrowid)
        except sqlite3.OperationalError as exc:
            if "readonly" in str(exc).lower():
                self._retry_with_fallback()
                with self._get_conn() as conn:
                    cur = conn.execute(
                        """
                        INSERT INTO wrong_questions (
                            question_text, answer_text, error_reason, source_type, image_path
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (question_text, answer_text, error_reason, source_type, image_path),
                    )
                    conn.commit()
                    return int(cur.lastrowid)
            raise

    def list_wrong_questions(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, question_text, answer_text, error_reason, source_type,
                       image_path, created_at, updated_at
                FROM wrong_questions
                ORDER BY id DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def list_wrong_questions_paginated(self, page: int = 1, page_size: int = 8) -> Dict[str, Any]:
        safe_page = max(int(page or 1), 1)
        safe_page_size = max(min(int(page_size or 8), 30), 1)

        with self._get_conn() as conn:
            total_row = conn.execute("SELECT COUNT(*) AS cnt FROM wrong_questions").fetchone()
            total = int(total_row["cnt"] if total_row else 0)
            total_pages = max((total + safe_page_size - 1) // safe_page_size, 1)
            if total > 0 and safe_page > total_pages:
                safe_page = total_pages

            offset = (safe_page - 1) * safe_page_size
            rows = conn.execute(
                """
                SELECT id, question_text, answer_text, error_reason, source_type,
                       image_path, created_at, updated_at
                FROM wrong_questions
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (safe_page_size, offset),
            ).fetchall()

        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
            "total_pages": total_pages,
            "has_prev": safe_page > 1 and total > 0,
            "has_next": safe_page < total_pages,
        }

    def get_wrong_question(self, record_id: int) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT id, question_text, answer_text, error_reason, source_type,
                       image_path, created_at, updated_at
                FROM wrong_questions
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_wrong_question(
        self,
        record_id: int,
        question_text: Any,
        answer_text: Any,
        error_reason: Any,
    ) -> bool:
        question_text = self._to_text(question_text)
        answer_text = self._to_text(answer_text)
        error_reason = self._to_text(error_reason)

        try:
            with self._get_conn() as conn:
                cur = conn.execute(
                    """
                    UPDATE wrong_questions
                    SET question_text = ?,
                        answer_text = ?,
                        error_reason = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (question_text, answer_text, error_reason, record_id),
                )
                conn.commit()
                return cur.rowcount > 0
        except sqlite3.OperationalError as exc:
            if "readonly" in str(exc).lower():
                self._retry_with_fallback()
                with self._get_conn() as conn:
                    cur = conn.execute(
                        """
                        UPDATE wrong_questions
                        SET question_text = ?,
                            answer_text = ?,
                            error_reason = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (question_text, answer_text, error_reason, record_id),
                    )
                    conn.commit()
                    return cur.rowcount > 0
            raise

    def delete_wrong_question(self, record_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                cur = conn.execute("DELETE FROM wrong_questions WHERE id = ?", (record_id,))
                conn.commit()
                return cur.rowcount > 0
        except sqlite3.OperationalError as exc:
            if "readonly" in str(exc).lower():
                self._retry_with_fallback()
                with self._get_conn() as conn:
                    cur = conn.execute("DELETE FROM wrong_questions WHERE id = ?", (record_id,))
                    conn.commit()
                    return cur.rowcount > 0
            raise

    def count_wrong_questions(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM wrong_questions").fetchone()
            return int(row["cnt"] if row else 0)
