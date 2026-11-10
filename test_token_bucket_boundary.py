import csv
import os
from datetime import datetime
import redis
import time
import threading
from concurrent.futures import ThreadPoolExecutor

BUCKET_CAPACITY = 10
REFILL_RATE = 10 / 60

BATCH_SIZE = 10
GAP_SECONDS = 1.9   # wait between the two batches (about 2 seconds in total)
TRIALS = 10

CSV_FILE = os.path.join("results", "token_bucket_boundary.csv")

client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

with open("atomic_token_bucket.lua", "r") as file:
    lua_script = file.read()

atomic_token_bucket = client.register_script(lua_script)


def send_request(key, phase, barrier):
    # Wait until all 10 workers are ready, then send together
    barrier.wait()

    request_time = time.time()

    result = atomic_token_bucket(
        keys=[key],
        args=[BUCKET_CAPACITY, REFILL_RATE]
    )

    return {
        "time": request_time,
        "phase": phase,
        "allowed": int(result[0]),
    }


def send_batch(key, phase):
    barrier = threading.Barrier(BATCH_SIZE)

    with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
        return list(
            executor.map(
                lambda _: send_request(key, phase, barrier),
                range(BATCH_SIZE)
            )
        )


def run_trial(run_id, trial):
    # New key for every trial. The key is empty, so the Lua script
    # creates a full bucket (10 tokens) using the Redis clock.
    key = f"research:token_bucket:boundary:{run_id}:{trial}"
    client.delete(key)

    first_batch = send_batch(key, "first")

    time.sleep(GAP_SECONDS)

    second_batch = send_batch(key, "second")

    client.delete(key)

    results = first_batch + second_batch
    span = max(r["time"] for r in results) - min(r["time"] for r in results)

    return results, span


if __name__ == "__main__":

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    print("Run ID:", run_id)

    rows = []
    summaries = []

    for trial in range(1, TRIALS + 1):
        results, span = run_trial(run_id, trial)

        first_allowed = sum(r["allowed"] for r in results if r["phase"] == "first")
        second_allowed = sum(r["allowed"] for r in results if r["phase"] == "second")

        summaries.append((first_allowed, second_allowed))

        print(
            "Trial", trial,
            "| first batch accepted:", first_allowed, "of", BATCH_SIZE,
            "| second batch accepted:", second_allowed, "of", BATCH_SIZE,
            "| total:", first_allowed + second_allowed,
            "| first-to-last request: %.3f s" % span
        )

        for r in results:
            rows.append({
                "run_id": run_id,
                "trial": trial,
                "timestamp": datetime.fromtimestamp(r["time"]).isoformat(
                    timespec="milliseconds"),
                "phase": r["phase"],
                "allowed": r["allowed"],
                "span_s": round(span, 3),
            })

    # Save all trials (append, one file for all runs)
    os.makedirs("results", exist_ok=True)
    write_header = not os.path.isfile(CSV_FILE) or os.path.getsize(CSV_FILE) == 0

    with open(CSV_FILE, "a", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["run_id", "trial", "timestamp", "phase",
                        "allowed", "span_s"]
        )

        if write_header:
            writer.writeheader()

        writer.writerows(rows)

    totals = [a + b for a, b in summaries]

    print("\n--- SUMMARY ---")
    print("Trials:", len(summaries))
    print("Total accepted per trial (out of 20):", totals)
    print("Saved to", CSV_FILE)

    client.close()