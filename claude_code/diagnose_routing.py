"""Diagnose why query intelligence is slow and routing incorrectly"""

import asyncio
import time
from src.agent.query_processing.query_intelligence import QueryIntelligence
from src.memory.session_manager import SessionManager

async def diagnose():
    print("=" * 80)
    print("DIAGNOSING QUERY INTELLIGENCE")
    print("=" * 80)
    print()

    # Test with fresh session (no context)
    session_id = "diagnose_test_123"
    query = "how do I upload photos"

    # Get conversation context
    session_manager = SessionManager()
    context_data = session_manager.get_context_for_llm(session_id)
    conversation_context = context_data.get("formatted_context", "")

    print(f"Query: '{query}'")
    print(f"Session ID: {session_id}")
    print(f"Conversation context length: {len(conversation_context)} chars")
    print(f"Conversation context: '{conversation_context[:200] if conversation_context else '(empty)'}...'")
    print()

    # Initialize query intelligence
    qi = QueryIntelligence()

    # Time the analysis
    print("Calling query_intelligence.analyze()...")
    start = time.time()

    analysis = await qi.analyze(
        query=query,
        query_type="howto",
        conversation_context=conversation_context,
        available_related_docs=[],
        session_id=session_id
    )

    elapsed_ms = (time.time() - start) * 1000

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"⏱️  Time taken: {elapsed_ms:.0f}ms")
    print()
    print(f"🔀 Routing decision: {analysis.routing}")
    print(f"   - is_followup: {analysis.is_followup}")
    print(f"   - can_answer_from_context: {analysis.can_answer_from_context}")
    print(f"   - matched_related_doc: {analysis.matched_related_doc}")
    print()
    print(f"📝 Enhanced query: '{analysis.structured_query.enhanced}'")
    print(f"   - category: {analysis.structured_query.category}")
    print(f"   - intent: {analysis.structured_query.user_intent}")
    print(f"   - tags: {analysis.structured_query.tags}")
    print()
    print(f"🎯 Confidence: {analysis.confidence}")
    print()

    # Analyze the issue
    print("=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    print()

    if elapsed_ms > 1800:
        print(f"⚠️  ISSUE: Query intelligence took {elapsed_ms:.0f}ms (expected ~1400ms)")
        print("   Possible causes:")
        print("   - Network latency to OpenAI API")
        print("   - Large conversation context being sent")
        print("   - Model processing time")
        print()

    if analysis.routing == "answer_from_context" and len(conversation_context.strip()) < 50:
        print(f"❌ CRITICAL: Routing to 'answer_from_context' with minimal conversation!")
        print(f"   Conversation context length: {len(conversation_context)} chars")
        print(f"   Expected routing: 'full_rag' (to search KB)")
        print()
        print("   This means:")
        print("   - No KB search will be performed")
        print("   - No embedding/search metrics")
        print("   - Response might not use your knowledge base content")
        print()
        print("   The LLM prompt may need adjustment to prevent this.")
        print()

    if analysis.routing == "full_rag":
        print(f"✅ CORRECT: Routing to 'full_rag' (will search KB)")
        print()

    # Check if there's cached conversation
    messages = session_manager.context_cache.get_messages(session_id, limit=10)
    if messages:
        print(f"⚠️  Found {len(messages)} cached messages in session!")
        print("   This might explain why it's routing to answer_from_context")
        print()
        for i, msg in enumerate(messages[:3]):
            print(f"   Message {i+1}: {msg.get('role')} - {msg.get('content', '')[:50]}...")
        print()

if __name__ == "__main__":
    asyncio.run(diagnose())
