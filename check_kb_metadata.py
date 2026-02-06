"""Check KB entry metadata to see if related_documents exists"""
import asyncio
from src.database.astra_client import AstraDBConnection

async def check_kb_metadata():
    """Check what metadata fields exist in KB entries"""
    db = AstraDBConnection()

    # Search for the "upload photos" entry
    results = await db.search(
        query_embedding=[0.1] * 1536,  # Dummy embedding
        collection_name="knowledgebase_entries",
        top_k=5,
        similarity_threshold=0.0  # Get anything
    )

    print("\n=== KB Entry Metadata Check ===\n")
    for i, result in enumerate(results, 1):
        title = result.get("title", "Unknown")
        metadata = result.get("metadata", {})

        print(f"{i}. {title}")
        print(f"   Metadata keys: {list(metadata.keys())}")
        print(f"   Related docs: {metadata.get('related_documents', 'NOT FOUND')}")
        print()

if __name__ == "__main__":
    asyncio.run(check_kb_metadata())
