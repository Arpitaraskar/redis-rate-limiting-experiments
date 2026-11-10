import csv
import os
from datetime import datetime
import redis
import time
import threading
from concurrent.futures import ThreadPoolExecutor

BUCKET_CAPACITY = 10
REFILL_RATE = 10 / 60

TOTAL_REQUESTS = 50
WORKERS = 50

KEY = "research:token_bucket:non_atomic"


def send_concurrent_request(barrier):

    # Each worker creates its own Redis connection
    client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True
    )

    try:
        # Wait until all workers are ready
        barrier.wait()

        # Read bucket state
        bucket = client.hgetall(KEY)

        current_time = time.time()

        tokens = float(bucket["tokens"])
        last_refill = float(bucket["last_refill"])

        # Calculate refill
        elapsed_time = current_time - last_refill
        refilled_tokens = elapsed_time * REFILL_RATE

        new_tokens = min(
            BUCKET_CAPACITY,
            tokens + refilled_tokens
        )

        # Consume token if available
        if new_tokens >= 1:
            new_tokens -= 1
            allowed = True
        else:
            allowed = False

        # Update Redis
        client.hset(
            KEY,
            mapping={
                "tokens": new_tokens,
                "last_refill": current_time
            }
        )

        return allowed

    finally:
        client.close()


if __name__ == "__main__":

    # Fresh bucket for this trial
    setup_client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True
    )

    setup_client.delete(KEY)

    setup_client.hset(
        KEY,
        mapping={
            "tokens": BUCKET_CAPACITY,
            "last_refill": time.time()
        }
    )

    print("Initial bucket:", setup_client.hgetall(KEY))

    # Synchronize all 50 workers
    barrier = threading.Barrier(WORKERS)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:

        results = list(
            executor.map(
                lambda _: send_concurrent_request(barrier),
                range(TOTAL_REQUESTS)
            )
        )

    allowed = sum(results)
    rejected = TOTAL_REQUESTS - allowed

    print("Total requests:", TOTAL_REQUESTS)
    print("Concurrent workers:", WORKERS)
    print("Allowed requests:", allowed)

   
print("Rejected requests:", rejected)

final_bucket = setup_client.hgetall(KEY)
print("Final bucket:", final_bucket)

# Save experiment result to CSV
os.makedirs("results", exist_ok=True)

csv_file = os.path.join("results", "non_atomic_results.csv")

file_exists = os.path.isfile(csv_file)

with open(csv_file, "a", newline="") as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "timestamp",
            "total_requests",
            "workers",
            "allowed",
            "rejected",
            "final_tokens"
        ]
    )

    if not file_exists:
        writer.writeheader()

    writer.writerow({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "total_requests": TOTAL_REQUESTS,
        "workers": WORKERS,
        "allowed": allowed,
        "rejected": rejected,
        "final_tokens": final_bucket.get("tokens")
    })

print("Results saved to:", csv_file)

setup_client.close()
