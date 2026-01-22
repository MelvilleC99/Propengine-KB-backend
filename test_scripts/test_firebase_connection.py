#!/usr/bin/env python3
"""Quick test of Firebase connection"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.firebase_client import initialize_firebase, test_firebase_connection
import asyncio

async def main():
    print("🔥 Testing Firebase connection...")
    print()
    
    try:
        # Initialize
        print("1️⃣ Initializing Firebase...")
        client = initialize_firebase()
        print(f"   ✅ Client created: {client}")
        print()
        
        # Test connection
        print("2️⃣ Testing connection...")
        success = await test_firebase_connection()
        
        if success:
            print("   ✅ Firebase connection working!")
        else:
            print("   ❌ Firebase connection failed!")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
