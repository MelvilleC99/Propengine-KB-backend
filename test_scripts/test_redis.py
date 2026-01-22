"""Test Redis Connection

Simple script to verify Redis connection works with your .env settings.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import redis

# Load environment variables
load_dotenv()

def test_redis_connection():
    """Test Redis connection"""
    
    print("=" * 60)
    print("TESTING REDIS CONNECTION")
    print("=" * 60)
    
    # Get Redis config from environment
    redis_host = os.getenv('REDIS_HOST')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_password = os.getenv('REDIS_PASSWORD')
    redis_db = int(os.getenv('REDIS_DB', 0))
    redis_ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'
    
    print(f"\n📋 Configuration:")
    print(f"   Host: {redis_host}")
    print(f"   Port: {redis_port}")
    print(f"   Database: {redis_db}")
    print(f"   SSL: {redis_ssl}")
    print(f"   Password: {'*' * len(redis_password) if redis_password else 'None'}")
    
    try:
        print(f"\n🔌 Connecting to Redis...")
        
        # Create Redis connection
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            ssl=redis_ssl,
            decode_responses=True,  # Return strings instead of bytes
            socket_connect_timeout=5
        )
        
        # Test connection
        print("   Testing PING...")
        response = r.ping()
        print(f"   ✅ PING response: {response}")
        
        # Test SET
        print("\n📝 Testing SET command...")
        r.set('test_key', 'Hello from PropEngine!')
        print("   ✅ SET successful")
        
        # Test GET
        print("\n📖 Testing GET command...")
        value = r.get('test_key')
        print(f"   ✅ GET successful: '{value}'")
        
        # Test SETEX (with expiration)
        print("\n⏰ Testing SETEX command (5 second expiration)...")
        r.setex('temp_key', 5, 'This will expire')
        ttl = r.ttl('temp_key')
        print(f"   ✅ SETEX successful (TTL: {ttl} seconds)")
        
        # Test EXISTS
        print("\n🔍 Testing EXISTS command...")
        exists = r.exists('test_key')
        print(f"   ✅ EXISTS successful: {exists}")
        
        # Test DEL
        print("\n🗑️  Testing DEL command...")
        r.delete('test_key')
        exists_after = r.exists('test_key')
        print(f"   ✅ DEL successful (exists after delete: {exists_after})")
        
        # Get Redis info
        print("\n📊 Redis Server Info:")
        info = r.info('server')
        print(f"   Redis Version: {info.get('redis_version')}")
        print(f"   OS: {info.get('os')}")
        print(f"   Uptime: {info.get('uptime_in_days')} days")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nRedis connection is working correctly! 🎉")
        
    except redis.ConnectionError as e:
        print("\n" + "=" * 60)
        print("❌ CONNECTION ERROR")
        print("=" * 60)
        print(f"\nCould not connect to Redis: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check REDIS_HOST in .env is correct")
        print("   2. Check REDIS_PORT in .env is correct")
        print("   3. Check REDIS_PASSWORD in .env is correct")
        print("   4. Verify Redis Cloud database is active")
        print("   5. Check firewall/network settings")
        sys.exit(1)
        
    except redis.AuthenticationError as e:
        print("\n" + "=" * 60)
        print("❌ AUTHENTICATION ERROR")
        print("=" * 60)
        print(f"\nAuthentication failed: {e}")
        print("\n🔧 Fix: Check REDIS_PASSWORD in .env file")
        sys.exit(1)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR")
        print("=" * 60)
        print(f"\nUnexpected error: {e}")
        print(f"Type: {type(e).__name__}")
        sys.exit(1)
    
    finally:
        # Close connection
        try:
            r.close()
            print("\n🔌 Connection closed")
        except:
            pass


if __name__ == "__main__":
    test_redis_connection()
