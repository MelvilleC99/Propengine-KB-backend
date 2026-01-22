"""
Test script to check chunking in AstraDB
"""
import asyncio
from src.database.astra_client import AstraDBConnection

async def test_chunks():
    print("🔍 Testing chunks in AstraDB...\n")
    
    # Get AstraDB connection
    astra = AstraDBConnection()
    vector_store = astra.get_vector_store()
    
    # Search for the entry we just synced
    entry_id = "Jra86rkKczhuiWP2Y0ab"
    
    print(f"Searching for chunks with parent_entry_id: {entry_id}\n")
    
    # Do a similarity search (dummy query to get results)
    results = vector_store.similarity_search(
        "listing",  # Simple query
        k=10,
        filter={"parent_entry_id": entry_id}
    )
    
    print(f"✅ Found {len(results)} chunks\n")
    print("=" * 80)
    
    for i, doc in enumerate(results):
        print(f"\n📄 CHUNK {i+1}:")
        print(f"Section Type: {doc.metadata.get('section_type', 'N/A')}")
        print(f"Chunk Index: {doc.metadata.get('chunk_index', 'N/A')}")
        print(f"Total Chunks: {doc.metadata.get('total_chunks', 'N/A')}")
        print(f"Position: {doc.metadata.get('context_position', 'N/A')}")
        print(f"Previous Section: {doc.metadata.get('context_previous_section', 'N/A')}")
        print(f"Next Section: {doc.metadata.get('context_next_section', 'N/A')}")
        print(f"\nContent Preview (first 200 chars):")
        print(doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content)
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_chunks())
