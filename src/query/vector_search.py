"""Vector search and query processing for AstraDB collections"""

from typing import List, Dict, Optional, Any
from langchain_astradb import AstraDBVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
import logging
from src.config.settings import settings

logger = logging.getLogger(__name__)

class VectorSearch:
    """Handles vector search operations using unified PropertyEngine collection with metadata filtering"""
    
    def __init__(self):
        """Initialize vector search with embeddings"""
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL
        )
        
        # Single unified collection configuration
        self.collection_name = settings.PROPERTY_ENGINE_COLLECTION
        self._vector_store = None
        
        # Entry type mappings for metadata filtering
        self.entry_type_map = {
            "definition": "definition",
            "error": "error", 
            "howto": "how_to",
            "workflow": "how_to"  # workflows are now how_to entries
        }
    
    def get_vector_store(self) -> AstraDBVectorStore:
        """Get or create the unified vector store with proper settings"""
        if not self._vector_store:
            logger.info(f"Creating vector store for unified collection: {self.collection_name}")
            
            self._vector_store = AstraDBVectorStore(
                token=settings.ASTRADB_TOKEN,
                api_endpoint=settings.ASTRADB_ENDPOINT,
                collection_name=self.collection_name,
                namespace=settings.ASTRADB_KEYSPACE,
                embedding=self.embeddings,
                metric="cosine",  # Ensure consistent similarity metric
                batch_size=1  # Reduce batch size for better compatibility
            )
        
        return self._vector_store
    
    async def search(
        self, 
        query: str, 
        entry_type: str = None,
        user_type: str = None, 
        k: int = 3,
        additional_metadata_filter: Optional[Dict] = None,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search the unified collection with metadata filtering"""
        try:
            vector_store = self.get_vector_store()
            
            # Build metadata filter
            metadata_filter = {}
            
            # Filter by entry type if specified
            if entry_type and entry_type in self.entry_type_map:
                metadata_filter["entryType"] = self.entry_type_map[entry_type]
            
            # Filter by user type if specified (internal, external, both)
            if user_type:
                metadata_filter["userType"] = user_type
            
            # Add any additional metadata filters
            if additional_metadata_filter:
                metadata_filter.update(additional_metadata_filter)
            
            logger.info(f"Searching with metadata filter: {metadata_filter}")
            
            # Perform similarity search with scores
            if metadata_filter:
                docs_with_scores = vector_store.similarity_search_with_score(
                    query,
                    k=k,
                    filter=metadata_filter
                )
            else:
                docs_with_scores = vector_store.similarity_search_with_score(query, k=k)
            
            # Filter by similarity threshold
            filtered_docs = [(doc, score) for doc, score in docs_with_scores if score >= similarity_threshold]
            
            logger.info(f"Found {len(filtered_docs)} results above threshold {similarity_threshold}")
            
            # Process results
            results = []
            for doc, score in filtered_docs:
                result = {
                    "content": self.extract_content(doc),
                    "metadata": doc.metadata if hasattr(doc, 'metadata') else {},
                    "entry_type": doc.metadata.get("entryType", "unknown") if hasattr(doc, 'metadata') else "unknown",
                    "user_type": doc.metadata.get("userType", "unknown") if hasattr(doc, 'metadata') else "unknown",
                    "similarity_score": score
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def extract_content(self, document: Document) -> str:
        """Extract content from document"""
        # Try page_content first (standard LangChain field)
        if hasattr(document, 'page_content') and document.page_content:
            return document.page_content
        
        # Try metadata['content'] (custom field)
        if hasattr(document, 'metadata') and document.metadata:
            if 'content' in document.metadata:
                return document.metadata['content']
            if 'text' in document.metadata:
                return document.metadata['text']
        
        logger.warning(f"Could not extract content from document")
        return ""
    
    def clean_query(self, query: str) -> str:
        """Clean and optimize query for vector search"""
        # Remove common stop words that don't help with search
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'why', 'when', 'where'}
        words = query.lower().split()
        cleaned = ' '.join([w for w in words if w not in stop_words])
        return cleaned if cleaned else query
