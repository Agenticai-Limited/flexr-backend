import os
import bcrypt
import configparser
from loguru import logger
from typing import Dict
from fastapi import HTTPException
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
from dataclasses import dataclass
from .models import NoResultLog
from .security import verify_password, get_password_hash

@dataclass
class NoResultLog:
    query: str
    username: str
    task_id: str

class PGDBUtil:
    _pool = None

    @classmethod
    def init_connection_pool(cls):
        """Initialize the connection pool"""
        if cls._pool is None:
            try:
                parser = configparser.ConfigParser()
                parser.read("db_config.ini")

                if parser.has_section("postgresql"):
                    db_params = dict(parser.items("postgresql"))
                    # Convert port to integer
                    db_params["port"] = int(db_params["port"])
                else:
                    raise Exception("postgresql not found in the app/db_config.ini")

                cls._pool = SimpleConnectionPool(1, 20, **db_params)
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
    def init_low_similarity_queries_table():
        """Initialize low_similarity_queries table if it doesn't exist"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS low_similarity_queries (
                        id SERIAL PRIMARY KEY,
                        query_type INTEGER NOT NULL CHECK (query_type IN (0, 1)),
                        col::TEXT NOT NULL,
                        query_content TEXT NOT NULL,
                        similarity_score FLOAT NOT NULL,
                        metric_type TEXT NOT NULL,
                        results TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Error initializing low_similarity_queries table: {e}")
            raise e

    @staticmethod
    def save_low_similarity_query(
        type: str,
        col: str,
        query: str,
        similarity_score: float,
        metric_type: str,
        results: str,
    ) -> bool:
        """Save no match query to PostgreSQL database"""
        try:

            query_type = 1 if type.lower() == "multimodal" else 0

            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_low_similarity_queries_table()

                cursor.execute(
                    """
                    INSERT INTO low_similarity_queries (query_type, col, query_content, similarity_score, metric_type, results)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (query_type, col, query, similarity_score, metric_type, results),
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
                        username TEXT NOT NULL,
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
                    INSERT INTO no_result_logs (query, username, task_id)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        no_result_log.query.strip(),
                        no_result_log.username,
                        no_result_log.task_id,
                    ),
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
        """Save QA interaction log to PostgreSQL database
        
        Args:
            task_id (str): The unique identifier for the QA task
            query (str): The user's question
            response (str): The AI's response
        """
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_qa_logs_table()

                cursor.execute(
                    """
                    INSERT INTO qa_logs (task_id, query, response)
                    VALUES (%s, %s, %s)
                    """,
                    (task_id, query.strip(), response.strip()),
                )
        except Exception as e:
            logger.error(f"Error saving QA log: {e}")
            raise e