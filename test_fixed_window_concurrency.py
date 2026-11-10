import csv
import os
from datetime import datetime
import redis
import time
import threading
from concurrent.futures import ThreadPoolExecutor

LIMIT = 10
EXPIRY = 60

TOTAL_REQUESTS = 20
WORKERS = 20
TRIALS = 25

CSV_FILE = os.path.join("results", "fixed_window_concurrency.csv")

client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

with open("fixed_window.lua", "r") as file:
    lua_script = file.read()

fixed_window = client.register_script(lua_script)


def send_concurrent_request(key, barrier):
    # Wait here until all workers are ready, then send together
    barrier.wait()

    result = fixed_window(keys=[key], args=[LIMIT, EXPIRY])

    return int(result[0]), int(result[1])


def run_trial(run_id, trial):
    # A new key for every trial, so trials never share a counter
    key = f"research:fixed_window:concurrency:{run_id}:{trial}"

    client.delete(key)

    barrier = threading.Barrier(WORKERS)

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        results = list(
            executor.map(
                lambda _: send_concurrent_request(key, barrier),
                range(TOTAL_REQUESTS)
            )
        )

    end_time = time.perf_counter()

    counts = sorted(count for count, status in results)
    allowed = sum(status for count, status in results)
    rejected = TOTAL_REQUESTS - allowed

    final_count = int(client.get(key))

    # Every request must get its own number from 1 to 20
    counts_ok = counts == list(range(1, TOTAL_REQUESTS + 1))

    client.delete(key)

    return {
        "run_id": run_id,
        "trial": trial,
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "total_requests": TOTAL_REQUESTS,
        "workers": WORKERS,
        "allowed": allowed,
        "rejected": rejected,
        "final_count": final_count,
        "counts_1_to_20": counts_ok,
        "duration": end_time - start_time,
    }


if __name__ == "__main__":

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    print("Run ID:", run_id)

    rows = []

    for trial in range(1, TRIALS + 1):
        row = run_trial(run_id, trial)
        rows.append(row)
        print(
            "Trial", trial,
            "| allowed:", row["allowed"],
            "| rejected:", row["rejected"],
            "| final count:", row["final_count"],
            "| counts 1-20:", row["counts_1_to_20"]
        )

    # Save all trials (append, one file for all runs)
    os.makedirs("results", exist_ok=True)
    write_header = not os.path.isfile(CSV_FILE) or os.path.getsize(CSV_FILE) == 0

    with open(CSV_FILE, "a", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "run_id",
                "trial",
                "timestamp",
                "total_requests",
                "workers",
                "allowed",
                "rejected",
                "final_count",
                "counts_1_to_20",
                "duration"
            ]
        )

        if write_header:
            writer.writeheader()

        writer.writerows(rows)

    all_ten = all(r["allowed"] == LIMIT for r in rows)
    all_counts = all(r["counts_1_to_20"] for r in rows)
    all_final = all(r["final_count"] == TOTAL_REQUESTS for r in rows)

    print("\n--- SUMMARY ---")
    print("Trials:", len(rows))
    print("Exactly", LIMIT, "allowed in every trial:", all_ten)
    print("Counts were 1 to 20 in every trial:", all_counts)
    print("Final counter was", TOTAL_REQUESTS, "in every trial:", all_final)
    print("Saved to", CSV_FILE)

    client.close()