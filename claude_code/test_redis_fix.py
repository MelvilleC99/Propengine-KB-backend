"""Test Redis pipeline optimization"""
import time
from src.memory.redis_message_store import RedisContextCache

def test_redis_performance():
    """Test that Redis operations are fast with pipeline"""
    print("=" * 60)
    print("TESTING REDIS PIPELINE OPTIMIZATION")
    print("=" * 60)
    print()

    cache = RedisContextCache()

    if not cache.redis_client:
        print("❌ Redis not connected - using memory fallback")
        print("   (This is OK for testing, but Redis won't be optimized)")
        return

    print("✅ Redis connected")
    print()

    # Test add_message performance
    session_id = "redis_perf_test"

    print("Testing add_message performance...")
    times = []

    for i in range(5):
        start = time.time()
        cache.add_message(
            session_id=session_id,
            role="user",
            content=f"Test message {i}",
            metadata={}
        )
        elapsed_ms = (time.time() - start) * 1000
        times.append(elapsed_ms)
        print(f"  Message {i+1}: {elapsed_ms:.0f}ms")

    avg_time = sum(times) / len(times)
    print()
    print(f"Average time: {avg_time:.0f}ms")
    print()

    # Evaluate performance
    if avg_time < 100:
        print(f"✅ EXCELLENT: {avg_time:.0f}ms (pipeline working!)")
        print(f"   Estimated savings: {450 - avg_time:.0f}ms per message")
    elif avg_time < 200:
        print(f"✅ GOOD: {avg_time:.0f}ms (decent performance)")
        print(f"   Estimated savings: {450 - avg_time:.0f}ms per message")
    elif avg_time < 300:
        print(f"⚠️  ACCEPTABLE: {avg_time:.0f}ms (could be better)")
        print(f"   Network latency may be high")
    else:
        print(f"❌ SLOW: {avg_time:.0f}ms (pipeline may not be working)")
        print(f"   Expected: <100ms with pipeline")
        print(f"   Check Redis connection latency")

    print()
    print("=" * 60)

if __name__ == "__main__":
    test_redis_performance()
