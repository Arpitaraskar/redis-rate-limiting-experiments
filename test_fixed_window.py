import redis
import time
from concurrent.futures import ThreadPoolExecutor

# Connect to Redis
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

# Load Lua script
with open("fixed_window.lua", "r") as file:
    lua_script = file.read()

fixed_window = redis_client.register_script(lua_script)

# Create one shared 60-second window
WINDOW_SIZE = 60
current_time = int(time.time())
window_id = current_time // WINDOW_SIZE

window_end = (window_id + 1) * WINDOW_SIZE
remaining_time = window_end - current_time

key = f"research:fixed_window:concurrency:{window_id}"

# Start with a fresh counter
redis_client.delete(key)

# Function executed by each concurrent request
def send_request():
    result = fixed_window(
        keys=[key],
        args=[10, remaining_time]
    )

    return result[0], result[1]


# Send 20 concurrent requests
with ThreadPoolExecutor(max_workers=20) as executor:
    results = list(executor.map(
        lambda _: send_request(),
        range(20)
    ))

# Analyse results
allowed = sum(1 for count, status in results if status == 1)
rejected = sum(1 for count, status in results if status == 0)

print("Total requests:", len(results))
print("Allowed requests:", allowed)
print("Rejected requests:", rejected)
print("Request counts:", sorted(count for count, status in results))