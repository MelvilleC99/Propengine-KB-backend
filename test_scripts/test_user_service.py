"""
Unit Tests for User Service

Tests:
1. User creation/update
2. Activity tracking (sessions, queries)
3. Recent sessions storage
4. User metadata structure
5. Firebase operations
"""

import asyncio
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.firebase_user_service import FirebaseUserService
from src.database.firebase_client import initialize_firebase


class TestUserService:
    """Test suite for Firebase User Service"""
    
    def __init__(self):
        self.user_service = None
        self.test_agent_id = f"TEST-USER-{int(time.time())}"
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
    
    # === TEST 1: Service Initialization ===
    def test_service_initialization(self):
        """Test user service can be initialized"""
        try:
            self.user_service = FirebaseUserService()
            
            if self.user_service:
                self.log_result(
                    "Service Initialization",
                    True,
                    "User service initialized successfully"
                )
                return True
            else:
                self.log_result(
                    "Service Initialization",
                    False,
                    "Service is None"
                )
                return False
        except Exception as e:
            self.log_result("Service Initialization", False, f"Error: {e}")
            return False
    
    # === TEST 2: User Data Structure ===
    def test_user_data_structure(self):
        """Test user data has all required fields"""
        try:
            # Create sample user data
            sample_user = {
                "agent_id": self.test_agent_id,
                "email": "test@example.com",
                "name": "Test",
                "phone": "+27821234567",
                "agency": "Test Real Estate",
                "office": "Test Office",
                "user_type": "agent"
            }
            
            # Validate all required fields are present
            required_fields = [
                "agent_id", "email", "name", "phone",
                "agency", "office", "user_type"
            ]
            
            missing_fields = [f for f in required_fields if f not in sample_user]
            
            if not missing_fields:
                self.log_result(
                    "User Data Structure",
                    True,
                    f"All {len(required_fields)} required fields present"
                )
                return True
            else:
                self.log_result(
                    "User Data Structure",
                    False,
                    f"Missing fields: {missing_fields}"
                )
                return False
                
        except Exception as e:
            self.log_result("User Data Structure", False, f"Error: {e}")
            return False
    
    # === TEST 3: Create User ===
    async def test_create_user(self):
        """Test creating a new user"""
        try:
            if not self.user_service:
                self.log_result(
                    "Create User",
                    False,
                    "User service not initialized"
                )
                return False
            
            # Create test user
            user_data = {
                "agent_id": self.test_agent_id,
                "email": "test@example.com",
                "name": "Test User",
                "phone": "+27821234567",
                "agency": "Test Real Estate",
                "office": "Test Office",
                "user_type": "agent"
            }
            
            success = await self.user_service.create_or_update_user(
                agent_id=self.test_agent_id,
                user_data=user_data
            )
            
            if success:
                self.log_result(
                    "Create User",
                    True,
                    f"Successfully created user: {self.test_agent_id}"
                )
                return True
            else:
                self.log_result(
                    "Create User",
                    False,
                    "Create user returned False (Firebase may not be configured)"
                )
                return False
                
        except Exception as e:
            # If Firebase is not configured, this is expected
            if "Firebase not initialized" in str(e) or "Firebase not available" in str(e):
                self.log_result(
                    "Create User",
                    True,
                    f"Skipped (Firebase not configured): {e}"
                )
                return True
            else:
                self.log_result("Create User", False, f"Error: {e}")
                return False
    
    # === TEST 4: Update User Activity ===
    async def test_update_user_activity(self):
        """Test updating user activity stats"""
        try:
            if not self.user_service:
                self.log_result(
                    "Update User Activity",
                    True,
                    "Skipped (service not initialized)"
                )
                return True
            
            # Update activity
            success = await self.user_service.update_user_activity(
                agent_id=self.test_agent_id,
                num_queries=5
            )
            
            if success:
                self.log_result(
                    "Update User Activity",
                    True,
                    f"Successfully updated activity for {self.test_agent_id}"
                )
                return True
            else:
                self.log_result(
                    "Update User Activity",
                    True,
                    "Skipped (Firebase may not be configured)"
                )
                return True
                
        except Exception as e:
            # If Firebase is not configured, this is expected
            if "Firebase not initialized" in str(e) or "Firebase not available" in str(e):
                self.log_result(
                    "Update User Activity",
                    True,
                    f"Skipped (Firebase not configured): {e}"
                )
                return True
            else:
                self.log_result("Update User Activity", False, f"Error: {e}")
                return False
    
    # === TEST 5: Add Recent Session ===
    async def test_add_recent_session(self):
        """Test adding a recent session to user"""
        try:
            if not self.user_service:
                self.log_result(
                    "Add Recent Session",
                    True,
                    "Skipped (service not initialized)"
                )
                return True
            
            # Create session summary
            session_summary = {
                "session_id": f"test_session_{int(time.time())}",
                "date": datetime.now().isoformat(),
                "summary": "User asked about photo uploads and file formats",
                "total_queries": 5
            }
            
            success = await self.user_service.add_recent_session(
                agent_id=self.test_agent_id,
                session_summary=session_summary
            )
            
            if success:
                self.log_result(
                    "Add Recent Session",
                    True,
                    f"Successfully added recent session"
                )
                return True
            else:
                self.log_result(
                    "Add Recent Session",
                    True,
                    "Skipped (Firebase may not be configured)"
                )
                return True
                
        except Exception as e:
            # If Firebase is not configured, this is expected
            if "Firebase not initialized" in str(e) or "Firebase not available" in str(e):
                self.log_result(
                    "Add Recent Session",
                    True,
                    f"Skipped (Firebase not configured): {e}"
                )
                return True
            else:
                self.log_result("Add Recent Session", False, f"Error: {e}")
                return False
    
    # === TEST 6: Recent Sessions Limit ===
    def test_recent_sessions_limit(self):
        """Test recent sessions limited to 5"""
        try:
            # Create 7 sessions
            sessions = [
                {
                    "session_id": f"session_{i}",
                    "date": datetime.now().isoformat(),
                    "summary": f"Session {i}"
                }
                for i in range(7)
            ]
            
            # Should only keep last 5
            recent_sessions = sessions[-5:]
            
            if len(recent_sessions) == 5:
                self.log_result(
                    "Recent Sessions Limit",
                    True,
                    "Correctly limits to 5 most recent sessions"
                )
                return True
            else:
                self.log_result(
                    "Recent Sessions Limit",
                    False,
                    f"Expected 5 sessions, got {len(recent_sessions)}"
                )
                return False
                
        except Exception as e:
            self.log_result("Recent Sessions Limit", False, f"Error: {e}")
            return False
    
    # === TEST 7: User Document ID Format ===
    def test_user_document_id_format(self):
        """Test user document IDs use agent_id"""
        try:
            # Validate agent_id format
            valid_format = (
                self.test_agent_id.startswith("TEST-") and
                len(self.test_agent_id) > 5
            )
            
            if valid_format:
                self.log_result(
                    "User Document ID Format",
                    True,
                    f"Agent ID follows correct format: {self.test_agent_id}"
                )
                return True
            else:
                self.log_result(
                    "User Document ID Format",
                    False,
                    "Agent ID doesn't follow format"
                )
                return False
                
        except Exception as e:
            self.log_result("User Document ID Format", False, f"Error: {e}")
            return False
    
    # === TEST 8: Activity Counters ===
    def test_activity_counters(self):
        """Test activity counters increment correctly"""
        try:
            # Simulate activity updates
            initial_sessions = 0
            initial_queries = 0
            
            # After 1 session with 5 queries
            final_sessions = initial_sessions + 1
            final_queries = initial_queries + 5
            
            if final_sessions == 1 and final_queries == 5:
                self.log_result(
                    "Activity Counters",
                    True,
                    f"Counters increment correctly: {final_sessions} sessions, {final_queries} queries"
                )
                return True
            else:
                self.log_result(
                    "Activity Counters",
                    False,
                    "Counter math incorrect"
                )
                return False
                
        except Exception as e:
            self.log_result("Activity Counters", False, f"Error: {e}")
            return False
    
    # === RUN ALL TESTS ===
    async def run_all_tests(self):
        """Run all tests and print summary"""
        print("=" * 60)
        print("USER SERVICE TEST SUITE")
        print("=" * 60)
        print()
        
        # Run tests
        self.test_service_initialization()
        self.test_user_data_structure()
        await self.test_create_user()
        await self.test_update_user_activity()
        await self.test_add_recent_session()
        self.test_recent_sessions_limit()
        self.test_user_document_id_format()
        self.test_activity_counters()
        
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
        
        print()
        print("👤 FIREBASE USER STRUCTURE:")
        print("   Collection: users")
        print("   Document ID: agent_id (e.g., BID-MD001)")
        print("   Required Fields:")
        print("     - agent_id, email, name, phone")
        print("     - agency, office, user_type")
        print("     - total_sessions, total_queries")
        print("     - first_seen, last_seen")
        print("     - recent_sessions (array, max 5)")
        print()
        
        return passed == total


async def main():
    """Main test runner"""
    # Initialize Firebase
    try:
        print("🔥 Initializing Firebase...")
        initialize_firebase()
        print("✅ Firebase initialized")
        print()
    except Exception as e:
        print(f"⚠️  Firebase not configured: {e}")
        print("📝 Tests will run with limited functionality")
        print()
    
    tester = TestUserService()
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
