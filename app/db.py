import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", {YOUR_DATABASE_URL})

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,  # Recycle connections every 5 minutes
    pool_size=10,  # Connection pool size
    max_overflow=20  # Maximum overflow connections
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database with pgvector extension and create tables"""
    logger.info("🔧 Initializing database...")
    
    try:
        # Test connection and enable pgvector extension
        with engine.connect() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            logger.info("✅ pgvector extension enabled successfully")
            
            # Test if vector type is available
            result = conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
            
    except Exception as e:
        logger.error(f"❌ Error enabling pgvector extension: {e}")
        raise
    
    # Import models here to avoid circular imports
    try:
        # Import all models to ensure they're registered with Base
        from .models import User, Document, ChatHistory
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise

def get_engine():
    """Get database engine"""
    return engine

def get_session():
    """Get a database session (for direct use, not dependency injection)"""
    return SessionLocal()

def test_database_connection():
    """Test database connection and pgvector extension"""
    try:
        with engine.connect() as conn:
            # Test basic connection
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"✅ PostgreSQL version: {version}")
            
            # Test pgvector extension
            result = conn.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """))
            extension_exists = result.fetchone()[0]
            
            if extension_exists:
                logger.info("✅ pgvector extension is available")
            else:
                logger.warning("❌ pgvector extension is NOT available")
                
            return True
            
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False

# Test connection on import (optional)
if __name__ == "__main__":
    test_database_connection()
    init_database()
