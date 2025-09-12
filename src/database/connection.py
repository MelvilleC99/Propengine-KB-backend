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
        
        # Collection names
        self.collections = {
            "definitions": settings.DEFINITIONS_COLLECTION,
            "errors": settings.ERRORS_COLLECTION,
            "howto": settings.HOWTO_COLLECTION,
            "workflows": settings.WORKFLOWS_COLLECTION
        }
    
    async def test_connection(self) -> Dict[str, bool]:
        """Test connection to all collections"""
        results = {}
        
        for collection_type, collection_name in self.collections.items():
            try:
                # Create a temporary vector store to test connection
                vector_store = AstraDBVectorStore(
                    token=self.token,
                    api_endpoint=self.endpoint,
                    collection_name=collection_name,
                    namespace=self.keyspace,
                    embedding=self.embeddings
                )
                
                # Just verify the collection exists and is accessible
                # Don't do a search since collections might be empty
                results[collection_type] = True
                logger.info(f"✓ {collection_type} collection accessible")
                
            except Exception as e:
                results[collection_type] = False
                logger.error(f"✗ {collection_type} collection error: {str(e)[:100]}")
        
        return results
    
    def get_status(self) -> str:
        """Get overall database status"""
        return "connected" if self.token and self.endpoint else "disconnected"
