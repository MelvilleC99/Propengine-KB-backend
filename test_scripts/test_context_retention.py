"""
Simple Test: Context Retention Across Multiple Messages

This tests if the agent remembers previous conversation context.
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.memory.session_manager import SessionManager
from src.memory.redis_message_store import RedisContextCache


async def test_context_retention():
    """Test if context is maintained across multiple messages"""
    
    print("=" * 70)
    print("CONTEXT RETENTION TEST")
    print("=" * 70)
    print()
    
    # Initialize
    session_manager = SessionManager()
    cache = RedisContextCache()
    test_session_id = f"context_test_{int(time.time())}"
    
    print(f"📝 Test Session ID: {test_session_id}")
    print()
    
    # === TEST 1: Check Redis Connection ===
    print("1️⃣  Checking Redis connection...")
    if cache.redis_client:
        try:
            cache.redis_client.ping()
            print("   ✅ Redis is connected and responding")
        except Exception as e:
            print(f"   ❌ Redis ping failed: {e}")
            return False
    else:
        print("   ⚠️  Redis client is None - using memory fallback")
    print()
    
    # === TEST 2: Add Messages ===
    print("2️⃣  Adding 3 messages to session...")
    
    messages = [
        {"role": "user", "content": "How do I upload photos?"},
        {"role": "assistant", "content": "Click the 'Add Photos' button in your listing editor."},
        {"role": "user", "content": "What about videos?"},
    ]
    
    for i, msg in enumerate(messages, 1):
        print(f"   Message {i}: {msg['role']} - {msg['content'][:50]}...")
        await session_manager.add_message(
            test_session_id,
            msg['role'],
            msg['content'],
            metadata={"test": True} if msg['role'] == "assistant" else None
        )
        await asyncio.sleep(0.1)  # Small delay
    
    print("   ✅ Messages added")
    print()
    
    # === TEST 3: Retrieve Messages from Redis ===
    print("3️⃣  Retrieving messages from Redis...")
    retrieved_messages = cache.get_messages(test_session_id, limit=10)
    
    if not retrieved_messages:
        print("   ❌ FAILED: No messages retrieved from Redis!")
        print("   This means context will be EMPTY!")
        return False
    
    print(f"   ✅ Retrieved {len(retrieved_messages)} messages")
    for i, msg in enumerate(retrieved_messages, 1):
        print(f"      {i}. {msg.get('role', 'unknown')}: {msg.get('content', '')[:60]}...")
    print()
    
    # === TEST 4: Get Context for LLM (What Agent Sees) ===
    print("4️⃣  Getting context formatted for LLM...")
    context_data = session_manager.get_context_for_llm(test_session_id)
    
    formatted_context = context_data.get("formatted_context", "")
    message_count = context_data.get("message_count", 0)
    has_summary = context_data.get("has_summary", False)
    
    print(f"   📊 Context Stats:")
    print(f"      - Message count: {message_count}")
    print(f"      - Has summary: {has_summary}")
    print(f"      - Formatted length: {len(formatted_context)} characters")
    print()
    
    if not formatted_context or len(formatted_context) < 10:
        print("   ❌ FAILED: Formatted context is EMPTY or too short!")
        print("   This means agent won't have conversation history!")
        return False
    
    print("   ✅ Context is populated")
    print()
    print("   📄 Formatted Context Preview:")
    print("   " + "─" * 66)
    preview_lines = formatted_context.split('\n')[:15]  # First 15 lines
    for line in preview_lines:
        print(f"   {line}")
    if len(formatted_context.split('\n')) > 15:
        print("   ... (truncated)")
    print("   " + "─" * 66)
    print()
    
    # === TEST 5: Verify Context Contains Messages ===
    print("5️⃣  Verifying context contains our messages...")
    
    checks = [
        ("Message 1 (user)", "upload photos" in formatted_context.lower()),
        ("Message 2 (assistant)", "add photos" in formatted_context.lower()),
        ("Message 3 (user)", "videos" in formatted_context.lower()),
    ]
    
    all_passed = True
    for check_name, check_result in checks:
        status = "✅" if check_result else "❌"
        print(f"   {status} {check_name}: {'Found' if check_result else 'NOT FOUND'}")
        if not check_result:
            all_passed = False
    print()
    
    if not all_passed:
        print("   ❌ FAILED: Context is missing some messages!")
        print("   Agent will NOT remember full conversation!")
        return False
    
    # === TEST 6: Add 4th Message and Check Context Updated ===
    print("6️⃣  Adding 4th message and checking context updates...")
    await session_manager.add_message(
        test_session_id,
        "assistant",
        "Yes, you can upload videos the same way. They must be under 50MB.",
        metadata={"test": True}
    )
    
    # Get updated context
    updated_context = session_manager.get_context_for_llm(test_session_id)
    updated_formatted = updated_context.get("formatted_context", "")
    
    if "50MB" in updated_formatted:
        print("   ✅ Context updated with new message")
    else:
        print("   ❌ Context NOT updated with new message")
        return False
    print()
    
    # === TEST 7: Simulate Real Scenario ===
    print("7️⃣  Simulating real scenario: User asks follow-up question...")
    print()
    print("   🗣️  Conversation:")
    print("   User: 'How do I upload photos?'")
    print("   Agent: 'Click the Add Photos button...'")
    print("   User: 'What about videos?'")
    print("   Agent: 'Yes, you can upload videos...'")
    print("   User: 'Can you remind me about photos again?'  ← FOLLOW-UP")
    print()
    
    # Get context that would be passed to LLM for this follow-up
    final_context = session_manager.get_context_for_llm(test_session_id)
    final_formatted = final_context.get("formatted_context", "")
    
    # Check if context has info to answer follow-up
    has_photo_context = "add photos" in final_formatted.lower()
    
    if has_photo_context:
        print("   ✅ SUCCESS: Agent has context to answer 'remind me about photos'")
        print("   Agent can see previous messages about photos!")
    else:
        print("   ❌ FAILED: Agent CANNOT answer follow-up question!")
        print("   Context doesn't contain previous photo discussion!")
        return False
    print()
    
    # === FINAL SUMMARY ===
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    if all_passed and has_photo_context:
        print("✅ ALL TESTS PASSED")
        print()
        print("Context Retention: WORKING ✅")
        print("- Messages are stored in Redis")
        print("- Context is retrieved correctly")
        print("- Context is formatted for LLM")
        print("- Agent can reference previous conversation")
        print()
        return True
    else:
        print("❌ TESTS FAILED")
        print()
        print("Context Retention: BROKEN ❌")
        print("- Check Redis connection")
        print("- Check session_manager.add_message()")
        print("- Check session_manager.get_context_for_llm()")
        print()
        return False


async def main():
    """Run the test"""
    try:
        success = await test_context_retention()
        sys.exit(0 if success else 1)
    except Exception as e:
        print()
        print(f"❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
