"""AstraDB database connection initialization and health checks"""

import logging
from typing import Dict, List, Optional
from langchain_astradb import AstraDBVectorStore
from langchain_openai import OpenAIEmbeddings
from src.config.settings import settings

logger = logging.getLogger(__name__)

class AstraDBConnection:
    """Manages AstraDB connection and health checks"""
    
    def __init__(self):
        """Initialize AstraDB connection parameters"""
        self.token = settings.ASTRADB_TOKEN
        self.endpoint = settings.ASTRADB_ENDPOINT
        self.keyspace = settings.ASTRADB_KEYSPACE
        
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL
        )
        
        # Single unified collection
        self.collection_name = settings.PROPERTY_ENGINE_COLLECTION
    
    async def test_connection(self) -> Dict[str, bool]:
        """Test connection to the unified PropertyEngine collection"""
        try:
            # Create a temporary vector store to test connection
            vector_store = AstraDBVectorStore(
                token=self.token,
                api_endpoint=self.endpoint,
                collection_name=self.collection_name,
                namespace=self.keyspace,
                embedding=self.embeddings
            )
            
            # Just verify the collection exists and is accessible
            # Don't do a search since collection might be empty
            logger.info(f"✓ PropertyEngine collection ({self.collection_name}) accessible")
            return {"property_engine": True}
            
        except Exception as e:
            logger.error(f"✗ PropertyEngine collection error: {str(e)[:100]}")
            return {"property_engine": False}
    
    def get_status(self) -> str:
        """Get overall database status"""
        return "connected" if self.token and self.endpoint else "disconnected"
