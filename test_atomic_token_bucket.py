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

KEY = "research:token_bucket:atomic"

client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

with open("atomic_token_bucket.lua", "r") as file:
    lua_script = file.read()

atomic_token_bucket = client.register_script(lua_script)
def send_concurrent_request(barrier):

    try:
        barrier.wait()

        result = atomic_token_bucket(
            keys=[KEY],
            args=[
                BUCKET_CAPACITY,
                REFILL_RATE
            ]
        )

        allowed = int(result[0])

        return allowed

    except Exception as error:
        print("Request failed:", error)
        raise
if __name__ == "__main__":

    # Reset Redis state for this trial
    client.delete(KEY)

    # Initialize bucket with 10 tokens
    client.hset(
        KEY,
        mapping={
            "tokens": BUCKET_CAPACITY,
            "last_refill": time.time()
        }
    )

    print("Initial bucket:", client.hgetall(KEY))

    # Synchronize all workers
    barrier = threading.Barrier(WORKERS)

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:

        results = list(
            executor.map(
                lambda _: send_concurrent_request(barrier),
                range(TOTAL_REQUESTS)
            )
        )

    end_time = time.perf_counter()

    # Calculate results
    allowed = sum(results)
    rejected = TOTAL_REQUESTS - allowed

    final_bucket = client.hgetall(KEY)

    print("Total requests:", TOTAL_REQUESTS)
    print("Concurrent workers:", WORKERS)
    print("Allowed requests:", allowed)
    print("Rejected requests:", rejected)
    print("Final bucket:", final_bucket)

    # Save experiment result to CSV
    os.makedirs("results", exist_ok=True)

    csv_file = os.path.join("results", "atomic_results.csv")

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
                "final_tokens",
                "duration"
            ]
        )

        if not file_exists or os.path.getsize(csv_file) == 0:
            writer.writeheader()

        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_requests": TOTAL_REQUESTS,
            "workers": WORKERS,
            "allowed": allowed,
            "rejected": rejected,
            "final_tokens": final_bucket.get("tokens"),
            "duration": end_time - start_time
        })

    print("Results saved to:", csv_file)

    client.close()