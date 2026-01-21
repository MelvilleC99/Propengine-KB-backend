"""
Quick test script to verify metadata field consistency

Run this after the fix to ensure entryType is being used correctly
"""

import asyncio
from src.mcp.firebase import FirebaseMCP
from src.mcp.vector_sync import VectorSyncMCP
from src.mcp.astradb import AstraDBMCP

async def test_metadata_consistency():
    """Test that metadata fields are consistent after fix"""
    
    print("🧪 Testing Metadata Field Consistency\n")
    
    # Initialize MCPs
    firebase = FirebaseMCP()
    sync = VectorSyncMCP()
    astra = AstraDBMCP()
    
    # Create a test entry
    print("1️⃣ Creating test entry...")
    test_entry = {
        "type": "definition",
        "title": "Test Metadata Consistency",
        "content": "This is a test entry to verify metadata field naming",
        "metadata": {
            "category": "testing",
            "userType": "internal",
            "product": "property_engine"
        },
        "rawFormData": {
            "term": "Test Entry",
            "definition": "An entry created to test metadata consistency"
        }
    }
    
    result = await firebase.create_entry(test_entry)
    
    if not result["success"]:
        print(f"❌ Failed to create entry: {result.get('error')}")
        return
    
    entry_id = result["entry_id"]
    print(f"✅ Created entry: {entry_id}\n")
    
    # Sync to vector database
    print("2️⃣ Syncing to vector database...")
    sync_result = await sync.sync_entry_to_vector(entry_id)
    
    if not sync_result["success"]:
        print(f"❌ Failed to sync: {sync_result.get('error')}")
        return
    
    print(f"✅ Synced successfully\n")
    
    # Verify metadata in AstraDB
    print("3️⃣ Verifying metadata in AstraDB...")
    vectors_result = await astra.list_vectors(limit=1)
    
    if vectors_result["success"] and vectors_result["entries"]:
        entry = vectors_result["entries"][0]
        metadata = entry.get("metadata", {})
        
        print("📋 Metadata fields found:")
        print(f"   - entryType: {metadata.get('entryType', '❌ MISSING')}")
        print(f"   - userType: {metadata.get('userType', '❌ MISSING')}")
        print(f"   - category: {metadata.get('category', '❌ MISSING')}")
        print()
        
        # Check for old 'type' field
        if "type" in metadata:
            print("⚠️  WARNING: Old 'type' field still exists!")
            print(f"   Value: {metadata['type']}")
            print()
        
        # Verify correct field
        if "entryType" in metadata:
            print("✅ SUCCESS: 'entryType' field is present!")
            print(f"   Value: {metadata['entryType']}")
        else:
            print("❌ FAILURE: 'entryType' field is MISSING!")
            print("   The fix may not have been applied correctly.")
    
    # Clean up test entry
    print("\n4️⃣ Cleaning up test entry...")
    await firebase.delete_entry(entry_id)
    await astra.delete_vector(entry_id)
    print("✅ Cleanup complete\n")
    
    print("="*50)
    print("Test complete!")

if __name__ == "__main__":
    asyncio.run(test_metadata_consistency())
