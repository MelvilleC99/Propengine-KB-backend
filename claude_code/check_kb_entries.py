"""Check if KB entries exist in AstraDB"""

import asyncio
from src.database.astra_client import AstraDBConnection

async def check_kb():
    print("🔍 Checking AstraDB for KB entries...")
    print("=" * 60)

    db = AstraDBConnection()
    vector_store = db.get_vector_store()

    # Try a simple search
    try:
        # Search for anything with "photo" or "upload"
        results = vector_store.similarity_search("photo upload", k=5)

        print(f"✅ Found {len(results)} results for 'photo upload'")
        print()

        if results:
            print("📄 Sample results:")
            for i, doc in enumerate(results[:3], 1):
                print(f"\nResult {i}:")
                print(f"  Content preview: {doc.page_content[:100]}...")
                if hasattr(doc, 'metadata'):
                    print(f"  Metadata: {doc.metadata}")
        else:
            print("❌ NO RESULTS FOUND!")
            print("\n⚠️ This means:")
            print("  1. AstraDB is empty (no KB entries synced)")
            print("  2. Or the embedding model is different")
            print("  3. Or there are no entries matching 'photo upload'")
            print("\n💡 Next steps:")
            print("  - Check if you've synced KB entries to AstraDB")
            print("  - Run the sync script")
            print("  - Verify embedding model matches")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 This might mean:")
        print("  - AstraDB connection issue")
        print("  - Vector store not initialized")
        print("  - Collection doesn't exist")

if __name__ == "__main__":
    asyncio.run(check_kb())
