import os
import bcrypt
import configparser
from loguru import logger
from typing import Dict
from fastapi import HTTPException
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager


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
                        content TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Error initializing feedback table: {e}")
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
                hashed = bcrypt.hashpw("test".encode("utf-8"), bcrypt.gensalt())
                cursor.execute(
                    """
                    INSERT INTO users (username, password)
                    VALUES (%s, %s)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    ("test", hashed.decode("utf-8")),
                )
        except Exception as e:
            logger.error(f"Error initializing users table: {e}")
            raise e

    @staticmethod
    def authenticate_user(username: str, password: str) -> tuple[bool, str]:
        """Authenticate user against database
        Returns:
            tuple[bool, str]: A tuple containing the authentication result and any exception message
        """
        is_success = False
        exception_msg = None

        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_users_table()

                cursor.execute(
                    "SELECT password FROM users WHERE username = %s", (username,)
                )
                result = cursor.fetchone()

                if result and bcrypt.checkpw(
                    password.encode("utf-8"), result[0].encode("utf-8")
                ):
                    is_success = True
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            exception_msg = str(e)
        return is_success, exception_msg

    @staticmethod
    def save_feedback(feedback):
        """Save feedback data to PostgreSQL database"""
        try:
            with PGDBUtil.get_connection() as conn:
                cursor = conn.cursor()
                PGDBUtil.init_feedback_table()

                cursor.execute(
                    """
                    INSERT INTO feedback (message_id, liked, reason, content, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        feedback.messageId,
                        feedback.liked,
                        feedback.reason,
                        feedback.content,
                        feedback.metadata,
                    ),
                )
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            raise e

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
