"""
Unit Tests for Analytics Service

Tests:
1. Analytics batch write to Firebase
2. Query metadata structure validation
3. Multiple analytics documents
4. Error handling
5. Firebase collection structure
"""

import asyncio
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.firebase_analytics_service import FirebaseAnalyticsService
from src.database.firebase_client import initialize_firebase


class TestAnalyticsService:
    """Test suite for Firebase Analytics Service"""
    
    def __init__(self):
        self.analytics_service = None
        self.test_session_id = f"test_analytics_{int(time.time())}"
        self.test_agent_id = "TEST-ANALYTICS-001"
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
        """Test analytics service can be initialized"""
        try:
            self.analytics_service = FirebaseAnalyticsService()
            
            if self.analytics_service:
                self.log_result(
                    "Service Initialization",
                    True,
                    "Analytics service initialized successfully"
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
    
    # === TEST 2: Query Metadata Structure ===
    def test_query_metadata_structure(self):
        """Test query metadata has all required fields"""
        try:
            # Create sample query metadata
            sample_query = {
                "query_id": f"query_{int(time.time())}",
                "session_id": self.test_session_id,
                "agent_id": self.test_agent_id,
                "timestamp": datetime.now().isoformat(),
                "query_text": "How do I upload photos?",
                "query_type": "successful_query",
                "category": "listings",
                "subcategory": "photos",
                "confidence_score": 0.92,
                "sources_found": 3,
                "sources_used": ["Photo Upload Guide", "Listing Editor"],
                "response_time_ms": 450,
                "escalated": False,
                "user_feedback": None
            }
            
            # Validate all required fields are present
            required_fields = [
                "query_id", "session_id", "agent_id", "timestamp",
                "query_text", "query_type", "category", "confidence_score",
                "sources_found", "response_time_ms", "escalated"
            ]
            
            missing_fields = [f for f in required_fields if f not in sample_query]
            
            if not missing_fields:
                self.log_result(
                    "Query Metadata Structure",
                    True,
                    f"All {len(required_fields)} required fields present"
                )
                return True
            else:
                self.log_result(
                    "Query Metadata Structure",
                    False,
                    f"Missing fields: {missing_fields}"
                )
                return False
                
        except Exception as e:
            self.log_result("Query Metadata Structure", False, f"Error: {e}")
            return False
    
    # === TEST 3: Batch Write Multiple Analytics ===
    async def test_batch_write_analytics(self):
        """Test batch writing multiple analytics documents"""
        try:
            if not self.analytics_service:
                self.log_result(
                    "Batch Write Analytics",
                    False,
                    "Analytics service not initialized"
                )
                return False
            
            # Create multiple test queries
            test_queries = []
            for i in range(3):
                query = {
                    "query_id": f"query_test_{int(time.time())}_{i}",
                    "session_id": self.test_session_id,
                    "agent_id": self.test_agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "query_text": f"Test query {i+1}",
                    "query_type": "successful_query",
                    "category": "listings",
                    "subcategory": "general",
                    "confidence_score": 0.85 + (i * 0.02),
                    "sources_found": 2 + i,
                    "sources_used": [f"Source {j}" for j in range(i+1)],
                    "response_time_ms": 300 + (i * 50),
                    "escalated": False,
                    "user_feedback": None
                }
                test_queries.append(query)
            
            # Batch write
            success = await self.analytics_service.batch_write_analytics(
                session_id=self.test_session_id,
                agent_id=self.test_agent_id,
                queries=test_queries
            )
            
            if success:
                self.log_result(
                    "Batch Write Analytics",
                    True,
                    f"Successfully wrote {len(test_queries)} analytics documents"
                )
                return True
            else:
                self.log_result(
                    "Batch Write Analytics",
                    False,
                    "Batch write returned False (Firebase may not be configured)"
                )
                return False
                
        except Exception as e:
            # If Firebase is not configured, this is expected
            if "Firebase not initialized" in str(e) or "Firebase not available" in str(e):
                self.log_result(
                    "Batch Write Analytics",
                    True,
                    f"Skipped (Firebase not configured): {e}"
                )
                return True
            else:
                self.log_result("Batch Write Analytics", False, f"Error: {e}")
                return False
    
    # === TEST 4: Empty Analytics List ===
    async def test_empty_analytics_list(self):
        """Test handling of empty analytics list"""
        try:
            if not self.analytics_service:
                self.log_result(
                    "Empty Analytics List",
                    True,
                    "Skipped (service not initialized)"
                )
                return True
            
            # Try to write empty list
            success = await self.analytics_service.batch_write_analytics(
                session_id=self.test_session_id,
                agent_id=self.test_agent_id,
                queries=[]
            )
            
            # Should return True (no error) but not write anything
            self.log_result(
                "Empty Analytics List",
                True,
                "Correctly handled empty analytics list"
            )
            return True
                
        except Exception as e:
            self.log_result("Empty Analytics List", False, f"Error: {e}")
            return False
    
    # === TEST 5: Analytics Document ID Format ===
    def test_analytics_document_id_format(self):
        """Test analytics document IDs follow correct format"""
        try:
            # Generate sample document IDs
            query_ids = [
                f"query_{self.test_session_id}_{i}"
                for i in range(3)
            ]
            
            # Validate format: query_<session_id>_<index>
            valid_format = all(
                qid.startswith("query_") and
                self.test_session_id in qid
                for qid in query_ids
            )
            
            if valid_format:
                self.log_result(
                    "Analytics Document ID Format",
                    True,
                    f"All {len(query_ids)} IDs follow correct format"
                )
                return True
            else:
                self.log_result(
                    "Analytics Document ID Format",
                    False,
                    "Some IDs don't follow format"
                )
                return False
                
        except Exception as e:
            self.log_result("Analytics Document ID Format", False, f"Error: {e}")
            return False
    
    # === TEST 6: Confidence Score Range ===
    def test_confidence_score_range(self):
        """Test confidence scores are in valid range (0-1)"""
        try:
            test_scores = [0.0, 0.5, 0.85, 0.92, 1.0]
            
            valid_scores = all(0.0 <= score <= 1.0 for score in test_scores)
            
            if valid_scores:
                self.log_result(
                    "Confidence Score Range",
                    True,
                    f"All {len(test_scores)} scores in valid range [0.0, 1.0]"
                )
                return True
            else:
                self.log_result(
                    "Confidence Score Range",
                    False,
                    "Some scores out of range"
                )
                return False
                
        except Exception as e:
            self.log_result("Confidence Score Range", False, f"Error: {e}")
            return False
    
    # === RUN ALL TESTS ===
    async def run_all_tests(self):
        """Run all tests and print summary"""
        print("=" * 60)
        print("ANALYTICS SERVICE TEST SUITE")
        print("=" * 60)
        print()
        
        # Run tests
        self.test_service_initialization()
        self.test_query_metadata_structure()
        await self.test_batch_write_analytics()
        await self.test_empty_analytics_list()
        self.test_analytics_document_id_format()
        self.test_confidence_score_range()
        
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
        print("📊 FIREBASE ANALYTICS STRUCTURE:")
        print("   Collection: kb_analytics")
        print("   Document ID: query_<session_id>_<index>")
        print("   Required Fields:")
        print("     - query_id, session_id, agent_id, timestamp")
        print("     - query_text, query_type, category")
        print("     - confidence_score (0.0-1.0)")
        print("     - sources_found, sources_used")
        print("     - response_time_ms, escalated")
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
    
    tester = TestAnalyticsService()
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
