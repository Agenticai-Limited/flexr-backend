import os
from loguru import logger
from .dbutil import DBUtil
from .pg_dbutil import PGDBUtil

class DBFactory:
    @staticmethod
    def get_db_util():
        """Factory method to get the appropriate database utility based on configuration"""
        use_local_db = os.environ.get("USE_LOCAL_DB", "true").lower() == "true"
        
        if use_local_db:
            logger.info("Using local SQLite database")
            return DBUtil
        
        try:
            # Test PostgreSQL connection
            PGDBUtil.init_connection_pool()
            logger.info("Using PostgreSQL database")
            return PGDBUtil
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL, falling back to SQLite: {e}")
            return DBUtil