"""Flush stale rate limit keys and kill idle connections from Redis"""
import os
from dotenv import load_dotenv

load_dotenv()

import redis

redis_host = os.getenv('REDIS_HOST')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD')
redis_db = int(os.getenv('REDIS_DB', 0))
redis_ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'

print(f"Connecting to Redis at {redis_host}:{redis_port}...")

r = redis.Redis(
    host=redis_host,
    port=redis_port,
    password=redis_password,
    db=redis_db,
    ssl=redis_ssl,
    decode_responses=True,
    socket_connect_timeout=5,
    max_connections=1
)

r.ping()
print("✅ Connected\n")

# === Kill idle client connections ===
print("=== CLIENT CONNECTIONS ===")
clients = r.client_list()
my_id = r.client_id()
killed = 0

for client in clients:
    client_id = client.get('id')
    idle = int(client.get('idle', 0))
    addr = client.get('addr', '?')
    cmd = client.get('cmd', '?')

    # Skip ourselves
    if str(client_id) == str(my_id):
        print(f"  [SELF] id={client_id} addr={addr} idle={idle}s cmd={cmd}")
        continue

    print(f"  id={client_id} addr={addr} idle={idle}s cmd={cmd}", end="")

    # Kill connections idle for more than 10 seconds
    if idle > 10:
        try:
            r.client_kill_filter(_id=client_id)
            print(" → KILLED")
            killed += 1
        except Exception as e:
            print(f" → kill failed: {e}")
    else:
        print(" → active, keeping")

print(f"\nKilled {killed} idle connections")

# === Delete rate limit keys ===
print("\n=== RATE LIMIT KEYS ===")
rate_keys = r.keys("rate_limit:*")
if rate_keys:
    r.delete(*rate_keys)
    print(f"✅ Deleted {len(rate_keys)} rate limit keys")
else:
    print("No rate limit keys found")

# === Show final state ===
info = r.info("clients")
print(f"\n=== FINAL STATE ===")
print(f"Connected clients: {info.get('connected_clients', '?')}")
print(f"Max clients: {info.get('maxclients', '?')}")

r.close()
print("\n✅ Done. Now restart the backend.")
