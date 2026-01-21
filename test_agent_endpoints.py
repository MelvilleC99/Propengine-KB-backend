"""
Test script for the three new agent endpoints

Run this to verify endpoints are working correctly
"""

import asyncio
import httpx

BACKEND_URL = "http://localhost:8000"

async def test_agent_endpoints():
    """Test all three agent endpoints"""
    
    test_query = "what is an API key?"
    
    print("=" * 60)
    print("Testing Agent Endpoints")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: Test Agent
        print("\n1️⃣ Testing TEST AGENT (/api/agent/test)")
        print("-" * 60)
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/agent/test",
                json={"message": test_query},
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {response.status_code}")
                print(f"📝 Response: {data['response'][:100]}...")
                print(f"🎯 Confidence: {data.get('confidence')}")
                print(f"📊 Sources: {len(data.get('sources', []))}")
                print(f"🔍 Debug Info: {bool(data.get('debug'))}")
                if data.get('debug'):
                    print(f"   - Query Type: {data['debug'].get('query_type')}")
                    print(f"   - Search Attempts: {data['debug'].get('search_attempts')}")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        # Test 2: Support Agent
        print("\n2️⃣ Testing SUPPORT AGENT (/api/agent/support)")
        print("-" * 60)
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/agent/support",
                json={
                    "message": test_query,
                    "user_info": {
                        "email": "support@propengine.com",
                        "name": "Test Support Staff"
                    }
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {response.status_code}")
                print(f"📝 Response: {data['response'][:100]}...")
                print(f"🎯 Confidence: {data.get('confidence')}")
                print(f"📊 Sources: {len(data.get('sources', []))}")
                print(f"🔍 Debug Info: {bool(data.get('debug'))}")
                print(f"⚠️  Escalation: {data.get('requires_escalation')}")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        # Test 3: Customer Agent
        print("\n3️⃣ Testing CUSTOMER AGENT (/api/agent/customer)")
        print("-" * 60)
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/agent/customer",
                json={
                    "message": test_query,
                    "user_info": {
                        "email": "customer@example.com",
                        "name": "Test Customer"
                    }
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {response.status_code}")
                print(f"📝 Response: {data['response'][:100]}...")
                print(f"🎯 Confidence: {data.get('confidence', 'HIDDEN')}")
                print(f"📊 Sources: {len(data.get('sources', []))}")
                print(f"🔍 Debug Info: {bool(data.get('debug'))}")
                print(f"⚠️  Escalation: {data.get('requires_escalation')}")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print("\n✅ Expected Results:")
    print("   - Test Agent: Shows confidence, sources, debug info")
    print("   - Support Agent: Shows confidence, sources, NO debug")
    print("   - Customer Agent: NO confidence, NO sources, NO debug")
    print()

if __name__ == "__main__":
    asyncio.run(test_agent_endpoints())
