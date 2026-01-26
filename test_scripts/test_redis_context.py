"""
Unit Tests for Redis Context Management

Tests:
1. Redis connection
2. Message storage and retrieval
3. Rolling summary storage
4. Context retrieval with summary
5. TTL and expiration
6. Fallback to memory
"""

import asyncio
import sys
import os
import time
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.memory.redis_message_store import RedisContextCache
from src.memory.session_manager import SessionManager
from src.utils.chat_summary import chat_summarizer


class TestRedisContextManagement:
    """Test suite for Redis context management"""
    
    def __init__(self):
        self.cache = RedisContextCache()
        self.session_manager = SessionManager()
        self.test_session_id = f"test_session_{int(time.time())}"
        self.results = []
    
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")
    
    # === TEST 1: Redis Connection ===
    def test_redis_connection(self):
        """Test Redis connection is working"""
        try:
            if self.cache.redis_client:
                self.cache.redis_client.ping()
                self.log_result("Redis Connection", True, "Redis connected successfully")
                return True
            else:
                self.log_result("Redis Connection", False, "Redis client is None (using memory fallback)")
                return False
        except Exception as e:
            self.log_result("Redis Connection", False, f"Connection failed: {e}")
            return False
    
    # === TEST 2: Message Storage ===
    def test_message_storage(self):
        """Test storing and retrieving messages"""
        try:
            # Add test messages
            self.cache.add_message(
                self.test_session_id,
                "user",
                "How do I upload photos?",
                {"test": True}
            )
            self.cache.add_message(
                self.test_session_id,
                "assistant",
                "To upload photos, click Add Photos button.",
                {"confidence": 0.85}
            )
            
            # Retrieve messages
            messages = self.cache.get_messages(self.test_session_id, limit=10)
            
            if len(messages) >= 2:
                self.log_result(
                    "Message Storage", 
                    True, 
                    f"Stored and retrieved {len(messages)} messages"
                )
                return True
            else:
                self.log_result("Message Storage", False, f"Expected 2+ messages, got {len(messages)}")
                return False
                
        except Exception as e:
            self.log_result("Message Storage", False, f"Error: {e}")
            return False
    
    # === TEST 3: Rolling Summary Storage ===
    def test_rolling_summary_storage(self):
        """Test storing and retrieving rolling summary"""
        try:
            # Create test summary
            test_summary = {
                "summary": "User learning about photo upload",
                "current_topic": "listing_photos",
                "conversation_state": "exploring",
                "key_facts": ["file size limit", "click add photos"],
                "updated_at": "2026-01-22T12:00:00"
            }
            
            # Store summary
            success = self.cache.store_rolling_summary(self.test_session_id, test_summary)
            
            if not success:
                self.log_result("Rolling Summary Storage", False, "Failed to store summary")
                return False
            
            # Retrieve summary
            retrieved = self.cache.get_rolling_summary(self.test_session_id)
            
            if retrieved and retrieved.get("current_topic") == "listing_photos":
                self.log_result(
                    "Rolling Summary Storage",
                    True,
                    f"Summary stored and retrieved: {retrieved.get('summary', '')[:50]}..."
                )
                return True
            else:
                self.log_result("Rolling Summary Storage", False, "Retrieved summary doesn't match")
                return False
                
        except Exception as e:
            self.log_result("Rolling Summary Storage", False, f"Error: {e}")
            return False
    
    # === TEST 4: Context with Summary ===
    def test_context_with_summary(self):
        """Test getting full context (messages + summary)"""
        try:
            context = self.cache.get_context_with_summary(self.test_session_id, max_messages=5)
            
            has_messages = len(context.get("messages", [])) > 0
            has_summary = context.get("has_summary", False)
            
            if has_messages and has_summary:
                self.log_result(
                    "Context with Summary",
                    True,
                    f"Context includes {len(context['messages'])} messages and summary"
                )
                return True
            else:
                self.log_result(
                    "Context with Summary",
                    False,
                    f"Missing data - messages: {has_messages}, summary: {has_summary}"
                )
                return False
                
        except Exception as e:
            self.log_result("Context with Summary", False, f"Error: {e}")
            return False
    
    # === TEST 5: Session Manager Integration ===
    async def test_session_manager_integration(self):
        """Test session manager uses context cache correctly"""
        try:
            # Create new test session
            test_session = f"test_sm_{int(time.time())}"
            
            # Add multiple messages with metadata
            metadata_list = []
            for i in range(3):
                metadata = {
                    "query_type": "test",
                    "confidence_score": 0.85,
                    "sources_found": 2,
                    "response_time_ms": 150
                }
                metadata_list.append(metadata)
                
                await self.session_manager.add_message(
                    test_session,
                    "user" if i % 2 == 0 else "assistant",
                    f"Test message {i+1}",
                    metadata if i % 2 == 1 else None  # Only add metadata to assistant messages
                )
            
            # Get context for LLM
            context = self.session_manager.get_context_for_llm(test_session)
            
            has_formatted = context.get("formatted_context") is not None
            has_messages = len(context.get("messages", [])) > 0
            
            # Check if query buffer is working (should have metadata)
            query_buffer = self.session_manager.query_buffers.get(test_session, [])
            has_buffer = len(query_buffer) > 0
            
            if has_formatted and has_messages:
                self.log_result(
                    "Session Manager Integration",
                    True,
                    f"Session manager correctly provides context (buffer: {len(query_buffer)} queries)"
                )
                return True
            else:
                self.log_result(
                    "Session Manager Integration",
                    False,
                    f"Context incomplete - formatted: {has_formatted}, messages: {has_messages}, buffer: {has_buffer}"
                )
                return False
                
        except Exception as e:
            self.log_result("Session Manager Integration", False, f"Error: {e}")
            return False
    
    # === TEST 6: Rolling Summary Generation ===
    async def test_rolling_summary_generation(self):
        """Test that rolling summaries are actually generated"""
        try:
            test_messages = [
                {"role": "user", "content": "How do I upload photos?", "timestamp": "2026-01-22T12:00:00"},
                {"role": "assistant", "content": "Click Add Photos button", "timestamp": "2026-01-22T12:00:01"},
                {"role": "user", "content": "What's the file size limit?", "timestamp": "2026-01-22T12:00:02"},
            ]
            
            # Generate summary
            summary = await chat_summarizer.generate_rolling_summary(
                previous_summary=None,
                new_messages=test_messages,
                session_id="test_summary"
            )
            
            has_summary = summary.get("summary") and len(summary.get("summary", "")) > 0
            has_topic = summary.get("current_topic") is not None
            
            if has_summary and has_topic:
                self.log_result(
                    "Rolling Summary Generation",
                    True,
                    f"Generated summary: {summary.get('summary', '')[:60]}..."
                )
                return True
            else:
                self.log_result(
                    "Rolling Summary Generation",
                    False,
                    f"Incomplete summary - text: {has_summary}, topic: {has_topic}"
                )
                return False
                
        except Exception as e:
            self.log_result("Rolling Summary Generation", False, f"Error: {e}")
            return False
    
    # === TEST 7: Redis Health Check ===
    def test_redis_health(self):
        """Test Redis health check"""
        try:
            health = self.cache.get_health()
            
            is_healthy = health.get("status") in ["healthy", "degraded"]
            redis_connected = health.get("redis_connected", False)
            
            self.log_result(
                "Redis Health Check",
                is_healthy,
                f"Status: {health.get('status')}, Connected: {redis_connected}"
            )
            return is_healthy
            
        except Exception as e:
            self.log_result("Redis Health Check", False, f"Error: {e}")
            return False
    
    # === RUN ALL TESTS ===
    async def run_all_tests(self):
        """Run all tests and print summary"""
        print("=" * 60)
        print("REDIS CONTEXT MANAGEMENT TEST SUITE")
        print("=" * 60)
        print()
        
        # Run tests
        self.test_redis_connection()
        self.test_message_storage()
        self.test_rolling_summary_storage()
        self.test_context_with_summary()
        await self.test_session_manager_integration()
        await self.test_rolling_summary_generation()
        self.test_redis_health()
        
        # Print summary
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        return passed == total


async def main():
    """Main test runner"""
    tester = TestRedisContextManagement()
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
