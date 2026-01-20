"""AstraDB database connection initialization and health checks"""

import logging
from typing import Dict, List, Optional
from langchain_astradb import AstraDBVectorStore
from langchain_openai import OpenAIEmbeddings
from src.config.settings import settings

logger = logging.getLogger(__name__)

class AstraDBConnection:
    """Singleton AstraDB connection manager"""
    
    _instance = None
    _vector_store = None
    _embeddings = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize AstraDB connection parameters (only once)"""
        if hasattr(self, '_initialized'):
            return
            
        self.token = settings.ASTRADB_TOKEN
        self.endpoint = settings.ASTRADB_ENDPOINT
        self.keyspace = settings.ASTRADB_KEYSPACE
        
        logger.info("AstraDB connection manager initialized")
        self._initialized = True
    
    def get_embeddings(self):
        """Get or create embeddings instance (singleton)"""
        if self._embeddings is None:
            self._embeddings = OpenAIEmbeddings(
                openai_api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                model=settings.EMBEDDING_MODEL,
                dimensions=1536  # Match AstraDB collection
            )
            logger.info(f"OpenAI embeddings instance created with model: {settings.EMBEDDING_MODEL}")
        return self._embeddings
    
    def get_vector_store(self, collection_name: str = None):
        """Get or create vector store instance (singleton)"""
        if collection_name is None:
            collection_name = settings.PROPERTY_ENGINE_COLLECTION
            
        if self._vector_store is None:
            try:
                self._vector_store = AstraDBVectorStore(
                    embedding=self.get_embeddings(),
                    collection_name=collection_name,
                    token=self.token,
                    api_endpoint=self.endpoint,
                    namespace=self.keyspace,
                    setup_mode="off"  # Don't try to create collection, assume it exists
                )
                logger.info(f"✅ AstraDB vector store created for collection: {collection_name}")
            except Exception as e:
                logger.error(f"❌ Failed to create AstraDB vector store: {e}")
                logger.error(f"Collection: {collection_name}, Endpoint: {self.endpoint}, Keyspace: {self.keyspace}")
                raise
        return self._vector_store
    
    async def test_connection(self) -> Dict:
        """Test connection to AstraDB"""
        results = {}
        
        try:
            vector_store = self.get_vector_store()
            # Simple test - try to perform a basic operation
            test_results = await vector_store.asimilarity_search("test", k=1)
            results["property_engine"] = "connected"
            logger.info("✓ AstraDB connection test successful")
        except Exception as e:
            results["property_engine"] = f"error: {str(e)}"
            logger.error(f"✗ AstraDB connection test failed: {e}")
        
        return results
    
    def is_connected(self) -> bool:
        """Check if AstraDB connection is available"""
        try:
            return self._vector_store is not None
        except Exception:
            return False

# Global singleton instance
astradb_connection = AstraDBConnection()
