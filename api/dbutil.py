import sqlite3
from loguru import logger
from typing import Dict
from fastapi import HTTPException
import bcrypt


class DBUtil:
    @staticmethod
    def init_feedback_table():
        """Initialize feedback table if it doesn't exist"""
        try:
            conn = sqlite3.connect("local.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    liked BOOLEAN NOT NULL,
                    reason TEXT,
                    content TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
                """
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing feedback table: {e}")
            raise e

    @staticmethod
    def init_users_table():
        """Initialize users table if it doesn't exist"""
        try:
            conn = sqlite3.connect("local.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
                """
            )

            # Insert a test user if not exists
            hashed = bcrypt.hashpw("ap-southeast-2".encode("utf-8"), bcrypt.gensalt())
            cursor.execute(
                """
                INSERT OR IGNORE INTO users (username, password)
                VALUES (?, ?)
                """,
                ("test", hashed.decode("utf-8")),
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing users table: {e}")
            raise e

    @staticmethod
    def authenticate_user(username: str, password: str) -> dict:
        """Authenticate user against database

        Args:
            username (str): The username
            password (str): The password

        Returns:
            tuple[bool, str]: A tuple containing the authentication result and any exception message
        """
        is_success = False
        exception_msg = None
        try:
            conn = sqlite3.connect("local.db")
            cursor = conn.cursor()

            DBUtil.init_users_table()

            cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()

            if result and bcrypt.checkpw(
                password.encode("utf-8"), result[0].encode("utf-8")
            ):
                is_success = True
            else:
                exception_msg = "Invalid username or password"

        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            exception_msg = str(e)
        finally:
            conn.close()
        return {"is_success": is_success, "message": exception_msg}

    @staticmethod
    def save_feedback(feedback) -> Dict:
        """Save feedback data to SQLite database

        Args:
            message_id (str): The message ID
            liked (bool): Whether the message was liked
            reason (str): The reason for the feedback
            content (str): The content of the feedback

        Returns:
            Dict: Status of the save operation
        """
        try:
            conn = sqlite3.connect("local.db")
            cursor = conn.cursor()

            DBUtil.init_feedback_table()

            cursor.execute(
                """
                INSERT INTO feedback (message_id, liked, reason, content, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    feedback.messageId,
                    feedback.liked,
                    feedback.reason,
                    feedback.content,
                    feedback.metadata,
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            raise e

    @staticmethod
    def init_low_similarity_queries_table():
        """Initialize low_similarity_queries table if it doesn't exist"""
        try:
            conn = sqlite3.connect("local.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS low_similarity_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_type INTEGER NOT NULL CHECK (query_type IN (0, 1)), 
                    col TEXT NOT NULL,
                    query_content TEXT NOT NULL,
                    similarity_score FLOAT NOT NULL,
                    metric_type TEXT NOT NULL,
                    results TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
                """
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing low_similarity_queries table: {e}")
            raise e

    @staticmethod
    def save_low_similarity_query(
        type: str, col: str, query: str, similarity_score: float, metric_type: str, results: str
    ) -> bool:
        """Save low similarity query to SQLite database
        Args:
            type (str): type of query, either "text" or "multimodal"
            col (str): collection name
            query (str): User's query
            similarity_score FLOAT,
            metric_type: IP or COSINE
            results (str),
        Returns:
            Dict: Status of the save operation
        """
        try:
            query_type = 1 if type.lower() == "multimodal" else 0

            conn = sqlite3.connect("local.db")
            cursor = conn.cursor()

            DBUtil.init_low_similarity_queries_table()

            cursor.execute(
                """
                INSERT INTO low_similarity_queries (query_type, col, query_content, similarity_score,metric_type, results)
                VALUES (?, ?, ?, ?, ?,?)
                """,
                (query_type, col, query, similarity_score, metric_type, results),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error saving no match query: {e}")
            raise e
