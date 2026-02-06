"""Test script to verify source attribution in KB context"""

import asyncio
from src.agent.context.context_builder import ContextBuilder

# Mock search result with metadata (like what comes from AstraDB)
mock_results = [
    {
        "entry_id": "test_chunk_123",
        "parent_entry_id": "test_kb_456",
        "content": "To upload photos in PropertyEngine, navigate to the Photos section and click Upload. Select your images and confirm.",
        "entry_type": "how_to",
        "similarity_score": 0.92,
        "metadata": {
            "parent_title": "Upload Photos Guide",
            "title": "Upload Photos Guide",
            "entryType": "how_to",
            "userType": "internal",
            "category": "photos",
            "related_documents": [
                "Photo Resizing Guide",
                "Image Quality Best Practices",
                "Troubleshooting Upload Errors"
            ]
        }
    },
    {
        "entry_id": "test_chunk_789",
        "parent_entry_id": "test_kb_999",
        "content": "Supported photo formats include JPG, PNG, and HEIC. Maximum file size is 10MB per photo.",
        "entry_type": "how_to",
        "similarity_score": 0.85,
        "metadata": {
            "parent_title": "Photo Formats Guide",
            "title": "Photo Formats Guide",
            "entryType": "how_to",
            "userType": "internal",
            "category": "photos",
            "related_documents": [
                "File Compression Tips",
                "Image Optimization"
            ]
        }
    }
]

def test_source_attribution():
    """Test the new source attribution formatting"""
    print("=" * 80)
    print("TESTING SOURCE ATTRIBUTION")
    print("=" * 80)
    print()

    # Test 1: Format contexts with sources
    print("TEST 1: Formatting contexts with source attribution")
    print("-" * 80)
    formatted = ContextBuilder.format_contexts_with_sources(mock_results, max_contexts=3)
    print(formatted)
    print()

    # Test 2: Check what LLM will see
    print("=" * 80)
    print("WHAT LLM WILL SEE IN KB CONTEXT:")
    print("=" * 80)
    print(formatted)
    print()

    # Verify key elements are present
    print("=" * 80)
    print("VERIFICATION:")
    print("=" * 80)
    checks = [
        ("Source titles present", "Upload Photos Guide" in formatted),
        ("Confidence scores present", "confidence:" in formatted),
        ("Entry type badges present", "[HOW_TO]" in formatted),
        ("Related documents present", "📌 Related Topics:" in formatted),
        ("Photo Resizing Guide mentioned", "Photo Resizing Guide" in formatted),
    ]

    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")

    print()
    print("=" * 80)

    all_passed = all(result for _, result in checks)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Source attribution is working!")
    else:
        print("⚠️ SOME TESTS FAILED - Check the output above")

    return all_passed

if __name__ == "__main__":
    test_source_attribution()
