
import redis
import time

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

BUCKET_CAPACITY = 10
REFILL_RATE = 10 / 60

key = "research:token_bucket:non_atomic"


def send_request(client, key):

    # 1. Read current bucket state from Redis
    bucket = client.hgetall(key)

    # 2. Get current values
    current_time = time.time()

    tokens = float(bucket["tokens"])
    last_refill = float(bucket["last_refill"])

    # 3. Calculate elapsed time
    elapsed_time = current_time - last_refill

    # 4. Refill tokens
    refilled_tokens = elapsed_time * REFILL_RATE

    new_tokens = min(
        BUCKET_CAPACITY,
        tokens + refilled_tokens
    )

    # 5. Check and consume a token
    if new_tokens >= 1:
        new_tokens -= 1
        allowed = True
    else:
        allowed = False

    # 6. Save updated state in Redis
    client.hset(
        key,
        mapping={
            "tokens": new_tokens,
            "last_refill": current_time
        }
    )

    return allowed, new_tokens


if __name__ == "__main__":

    # Reset Redis state for this test
    redis_client.delete(key)

    # Initialize bucket with 10 tokens
    redis_client.hset(
        key,
        mapping={
            "tokens": BUCKET_CAPACITY,
            "last_refill": time.time()
        }
    )

    print("Initial Redis state:", redis_client.hgetall(key))

    # Send one request
    allowed, remaining_tokens = send_request(redis_client, key)

    print("Request allowed:", allowed)
    print("Remaining tokens:", remaining_tokens)
    print("Final Redis state:", redis_client.hgetall(key))

    print("Redis connected:", redis_client.ping())
