import os
import bcrypt
from loguru import logger
from typing import Dict
from fastapi import HTTPException
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
from dataclasses import dataclass
from .models import NoResultLog
from .security import verify_password, get_password_hash
from src.flexr.utils.models import RerankedResult
import json

@dataclass
class NoResultLog:
    query: str
    task_id: str

class PGDBUtil:
    _pool = None

    @classmethod
    def init_connection_pool(cls):
        """Initialize the connection pool"""
        if cls._pool is None:
            try:
                database_url = os.environ["DATABASE_URL"]
                if not database_url:
                    raise Exception("DATABASE_URL not found in environment variables")

                cls._pool = SimpleConnectionPool(1, 20, dsn=database_url)
                logger.info("PostgreSQL connection pool initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing PostgreSQL connection pool: {e}")
                raise e

    @classmethod
    @contextmanager
    def get_connection(cls):
        """Get a connection from the pool"""
        if cls._pool is None:
            cls.init_connection_pool()
        conn = cls._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cls._pool.putconn(conn)

    @staticmethod
    def init_feedback_table():
        """Initialize feedback table if it doesn't exist"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        id SERIAL PRIMARY KEY,
                        message_id TEXT NOT NULL,
                        liked BOOLEAN NOT NULL,
                        reason TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Error initializing feedback table: {e}")
            raise e

    @staticmethod
    def add_user(username: str, password: str):
        """Add a new user to the database"""
        try:
            hashed_password = get_password_hash(password)
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, password)
                    VALUES (%s, %s)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    (username, hashed_password),
                )
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            raise e

    @staticmethod
    def init_users_table():
        """Initialize users table if it doesn't exist"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        is_admin BOOLEAN DEFAULT FALSE,
                        full_name TEXT DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Insert test user if not exists
                hashed_password = get_password_hash("aTt8mZ9x0kzh222")
                cursor.execute(
                    """
                    INSERT INTO users (username, password)
                    VALUES (%s, %s)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    ("test", hashed_password),
                )
        except Exception as e:
            logger.error(f"Error initializing users table: {e}")
            raise e

    @staticmethod
    def authenticate_user(username: str, password: str) -> bool:
        """Authenticate user against database
        Returns:
            bool: Authentication result
        """
        with PGDBUtil.get_connection() as conn:
            cursor = conn.cursor()
            PGDBUtil.init_users_table()

            cursor.execute(
                "SELECT password FROM users WHERE username = %s", (username,)
            )
            result = cursor.fetchone()

            if result and verify_password(password, result[0]):
                return True
            else:
                return False

    @staticmethod
    def save_feedback(feedback):
        """Save feedback data to PostgreSQL database"""
        with PGDBUtil.get_connection() as conn:
            cursor = conn.cursor()
            PGDBUtil.init_feedback_table()

            cursor.execute(
                """
                INSERT INTO feedback (message_id, liked, reason)
                VALUES (%s, %s, %s)
                """,
                (
                    feedback.messageId,
                    feedback.liked,
                    feedback.reason,
                ),
            )

    @staticmethod
    def init_low_relevance_results_table():
        """Initialize low_relevance_results table if it doesn't exist"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS low_relevance_results (
                        id SERIAL PRIMARY KEY,
                        query TEXT NOT NULL,
                        original_index INTEGER NOT NULL,
                        relevance_score FLOAT NOT NULL,
                        content TEXT,
                        page_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Error initializing low_relevance_results table: {e}")
            raise e

    @staticmethod
    def save_low_relevance_result(
        query: str,
        origin_index: int,
        relevance_score: float,
        content: str,
        page_id: str = None,
    ) -> bool:
        """Save low relevance result after rerank to PostgreSQL database"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_low_relevance_results_table()

                cursor.execute(
                    """
                    INSERT INTO low_relevance_results (query, original_index, relevance_score, content, page_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (query, origin_index, relevance_score, content, page_id),
                )
        except Exception as e:
            logger.error(f"Error saving no match query: {e}")
            raise e

    @staticmethod
    def init_no_result_logs_table():
        """Initialize no_result_logs table if it doesn't exist"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS no_result_logs (
                        id SERIAL PRIMARY KEY,
                        query TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Error initializing no_result_logs table: {e}")
            raise e

    @staticmethod
    def save_no_result_query(no_result_log: NoResultLog):
        """Save no result query to PostgreSQL database"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_no_result_logs_table()

                cursor.execute(
                    """
                    INSERT INTO no_result_logs (query, task_id)
                    VALUES (%s, %s)
                    """,
                    (no_result_log.query, no_result_log.task_id),
                )
        except Exception as e:
            logger.error(f"Error saving no result query: {e}")
            raise e

    @staticmethod
    def init_qa_logs_table():
        """Initialize qa_logs table if it doesn't exist"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS qa_logs (
                        id SERIAL PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        query TEXT NOT NULL,
                        response TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Error initializing qa_logs table: {e}")
            raise e

    @staticmethod
    def save_qa_log(task_id: str, query: str, response: str):
        """Save QA log to PostgreSQL database"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_qa_logs_table()

                cursor.execute(
                    """
                    INSERT INTO qa_logs (task_id, query, response)
                    VALUES (%s, %s, %s)
                    """,
                    (task_id, query, response),
                )
        except Exception as e:
            logger.error(f"Error saving QA log: {e}")
            raise e

    @staticmethod
    def save_reranked_results(task_id: str, results: list[RerankedResult]):
        """Save reranked results to PostgreSQL database"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_reranked_results_table()
                
                for result in results:
                    cursor.execute(
                        """
                        INSERT INTO rerank_results (task_id, original_index, content, relevance, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            task_id,
                            result.original_index,
                            result.content,
                            result.relevance,
                            json.dumps(result.metadata),
                        ),
                    )
        except Exception as e:
            logger.error(f"Error saving reranked results: {e}")
            raise e

    @staticmethod
    def init_reranked_results_table():
        """Initialize rerank_result table if it doesn't exist"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rerank_results (
                        id SERIAL PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        original_index INTEGER NOT NULL,
                        content TEXT,
                        relevance FLOAT NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Error initializing rerank_result table: {e}")
            raise e
    