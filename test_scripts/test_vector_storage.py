#!/usr/bin/env python3
"""Test AstraDB vector storage and search"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.astra_client import AstraDBConnection
from src.config.settings import settings
import asyncio

async def test_astradb_storage():
    print("=" * 60)
    print("Testing AstraDB Vector Storage")
    print("=" * 60)
    
    # Initialize connection
    astra = AstraDBConnection()
    vector_store = astra.get_vector_store()
    
    print("\n1. Checking documents in collection...")
    print("-" * 60)
    
    # Get all documents (no filter)
    try:
        results = vector_store.similarity_search(
            query="test",
            k=10,
            filter={}  # No metadata filter
        )
        
        print(f"✅ Total documents found: {len(results)}")
        
        if len(results) == 0:
            print("❌ No documents in collection!")
            print("\nPossible reasons:")
            print("  1. Frontend hasn't synced any entries yet")
            print("  2. Syncing failed silently")
            print("  3. Wrong collection name")
            return
        
        print("\n2. Document details:")
        print("-" * 60)
        for i, doc in enumerate(results, 1):
            print(f"\n📄 Document {i}:")
            print(f"   Content preview: {doc.page_content[:100]}...")
            print(f"   Metadata: {doc.metadata}")
            
    except Exception as e:
        print(f"❌ Error querying AstraDB: {e}")
        return
    
    print("\n3. Testing similarity search with 'upload photos'...")
    print("-" * 60)
    
    # Test with actual query
    query = "how do I upload photos"
    
    try:
        # Get embeddings for the query
        embeddings = astra.get_embeddings()
        query_embedding = embeddings.embed_query(query)
        print(f"✅ Generated query embedding, dimension: {len(query_embedding)}")
        
        # Search with different thresholds
        for threshold in [0.5, 0.6, 0.7, 0.8, 0.9]:
            results = vector_store.similarity_search_with_score(
                query=query,
                k=5,
                filter={}
            )
            
            matches_above_threshold = [
                (doc, score) for doc, score in results if score >= threshold
            ]
            
            print(f"\n   Threshold {threshold}: {len(matches_above_threshold)} results")
            
            for doc, score in matches_above_threshold[:3]:
                print(f"      - Score: {score:.3f}")
                print(f"        Title: {doc.metadata.get('title', 'No title')}")
                print(f"        Content: {doc.page_content[:80]}...")
                
    except Exception as e:
        print(f"❌ Error in similarity search: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_astradb_storage())
