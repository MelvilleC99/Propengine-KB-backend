"""Vector search and query processing for AstraDB collections"""

from typing import List, Dict, Optional, Any
from langchain_astradb import AstraDBVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
import logging
from src.config.settings import settings

logger = logging.getLogger(__name__)

class VectorSearch:
    """Handles vector search operations across different collections"""
    
    def __init__(self):
        """Initialize vector search with embeddings"""
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL
        )
        
        # Collection configurations with their specific field names
        self.collection_configs = {
            "definitions": {
                "name": settings.DEFINITIONS_COLLECTION,
                "content_field": "page_content"  # Uses page_content
            },
            "errors": {
                "name": settings.ERRORS_COLLECTION,
                "content_field": "page_content"
            },
            "howto": {
                "name": settings.HOWTO_COLLECTION,
                "content_field": "page_content"
            },
            "workflows": {
                "name": settings.WORKFLOWS_COLLECTION,
                "content_field": "content"  # Uses content (different from others!)
            }
        }
        
        self._vector_stores = {}
    
    def get_vector_store(self, collection_type: str) -> AstraDBVectorStore:
        """Get or create a vector store for a specific collection"""
        if collection_type not in self._vector_stores:
            config = self.collection_configs.get(collection_type)
            if not config:
                raise ValueError(f"Unknown collection type: {collection_type}")
            
            logger.info(f"Creating vector store for {collection_type}: {config['name']}")
            
            self._vector_stores[collection_type] = AstraDBVectorStore(
                token=settings.ASTRADB_TOKEN,
                api_endpoint=settings.ASTRADB_ENDPOINT,
                collection_name=config['name'],
                namespace=settings.ASTRADB_KEYSPACE,
                embedding=self.embeddings
            )
        
        return self._vector_stores[collection_type]
    
    async def search(
        self, 
        query: str, 
        collection_type: str, 
        k: int = 3,
        metadata_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Search a specific collection and return structured results"""
        try:
            vector_store = self.get_vector_store(collection_type)
            config = self.collection_configs[collection_type]
            
            # Perform similarity search
            if metadata_filter:
                docs = vector_store.similarity_search(
                    query,
                    k=k,
                    filter=metadata_filter
                )
            else:
                docs = vector_store.similarity_search(query, k=k)
            
            logger.info(f"Found {len(docs)} results in {collection_type}")
            
            # Process results based on collection's field structure
            results = []
            for doc in docs:
                result = {
                    "content": self.extract_content(doc, config['content_field']),
                    "metadata": doc.metadata if hasattr(doc, 'metadata') else {},
                    "collection": collection_type
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Search error in {collection_type}: {e}")
            return []
    
    def extract_content(self, document: Document, field_name: str) -> str:
        """Extract content from document based on field name"""
        # For workflow collection, content is in metadata['content']
        if field_name == "content" and hasattr(document, 'metadata'):
            if 'content' in document.metadata:
                return document.metadata['content']
        
        # For other collections, use page_content
        if field_name == "page_content" and hasattr(document, 'page_content'):
            return document.page_content
        
        # Fallback: try both approaches
        if hasattr(document, 'page_content') and document.page_content:
            return document.page_content
        
        if hasattr(document, 'metadata') and document.metadata:
            if 'content' in document.metadata:
                return document.metadata['content']
            if 'text' in document.metadata:
                return document.metadata['text']
        
        logger.warning(f"Could not extract content from document with field {field_name}")
        return ""
    
    def clean_query(self, query: str) -> str:
        """Clean and optimize query for vector search"""
        # Remove common stop words that don't help with search
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'why', 'when', 'where'}
        words = query.lower().split()
        cleaned = ' '.join([w for w in words if w not in stop_words])
        return cleaned if cleaned else query
