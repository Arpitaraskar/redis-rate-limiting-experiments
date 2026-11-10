import redis
import time

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

WINDOW_SIZE = 60

current_time = int(time.time())

window_id = current_time // WINDOW_SIZE

print("Current timestamp:", current_time)
print("Window ID:", window_id)

window_start = window_id * WINDOW_SIZE

window_end = window_start + WINDOW_SIZE

remaining_time = window_end - current_time

print("Remaining window time:", remaining_time)

key = f"research:fixed_window:{window_id}"

print("Redis key:", key)

print(redis_client.ping())

with open("fixed_window.lua", "r") as file:
    lua_script = file.read()

fixed_window = redis_client.register_script(lua_script)

result = fixed_window(
    keys=[key],
    args=[10, remaining_time]
)

count = result[0]
allowed = result[1]

if allowed == 1:
    print("request allowed")
else:
    print("request rejected")

print("Request count:", count)


ttl =  redis_client.ttl(key)

print("remainning TTL : ", ttl , "second")

