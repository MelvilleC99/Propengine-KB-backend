"""
Test search precision with chunking
"""
import asyncio
from src.database.astra_client import AstraDBConnection

async def test_search():
    print("🔍 Testing search precision with chunked entries...\n")
    
    astra = AstraDBConnection()
    vector_store = astra.get_vector_store()
    
    # Test different queries
    test_queries = [
        "What are the prerequisites?",
        "Show me the steps",
        "Give me an overview",
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"🔎 Query: '{query}'")
        print(f"{'='*80}\n")
        
        # Search with parent_entry_id filter
        results = vector_store.similarity_search_with_score(
            query,
            k=3,
            filter={"parent_entry_id": "Jra86rkKczhuiWP2Y0ab"}
        )
        
        for i, (doc, score) in enumerate(results):
            print(f"Result {i+1} (score: {score:.4f}):")
            print(f"  Section: {doc.metadata.get('section_type', 'N/A')}")
            print(f"  Position: {doc.metadata.get('context_position', 'N/A')}")
            print(f"  Content preview: {doc.page_content[:100]}...")
            print()

if __name__ == "__main__":
    asyncio.run(test_search())
