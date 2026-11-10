import redis
import time
import csv
import os
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

WINDOW_SIZE = 60
LIMIT = 10
KEY_PREFIX = "research:fixed_window:boundary"
CSV_FILE = os.path.join("results", "fixed_window_boundary_runs.csv")

client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

with open("fixed_window.lua", "r") as file:
    lua_script = file.read()

fixed_window = client.register_script(lua_script)


def send_request(phase):
    current_time = time.time()

    window_id = int(current_time // WINDOW_SIZE)
    window_end = (window_id + 1) * WINDOW_SIZE
    remaining_time = max(1, int(window_end - current_time))

    key = f"{KEY_PREFIX}:{window_id}"

    result = fixed_window(keys=[key], args=[LIMIT, remaining_time])

    return {
        "timestamp": current_time,
        "phase": phase,
        "window_id": window_id,
        "count": int(result[0]),
        "allowed": int(result[1]),
    }


def send_batch(phase):
    barrier = threading.Barrier(LIMIT)

    def worker(_):
        barrier.wait()
        return send_request(phase)

    with ThreadPoolExecutor(max_workers=LIMIT) as executor:
        return list(executor.map(worker, range(LIMIT)))


if __name__ == "__main__":

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    print("Run ID:", run_id)

    # Step 1: pick the next boundary (at least 5 seconds away)
    boundary = (int(time.time() // WINDOW_SIZE) + 1) * WINDOW_SIZE
    if boundary - time.time() < 5:
        boundary += WINDOW_SIZE

    before_window = int(boundary // WINDOW_SIZE) - 1
    after_window = before_window + 1
    before_key = f"{KEY_PREFIX}:{before_window}"
    after_key = f"{KEY_PREFIX}:{after_window}"

    # Step 2: clear both counters and check they are really empty
    client.delete(before_key, after_key)
    if client.exists(before_key) or client.exists(after_key):
        print("Could not clear the counters. Stop.")
        raise SystemExit(1)

    print("Next window boundary:", datetime.fromtimestamp(boundary))
    print("Counters cleared for windows", before_window, "and", after_window)

    # Step 3: wait until 2 seconds before the boundary
    while time.time() < boundary - 2:
        time.sleep(0.05)

    print("\nSending 10 requests BEFORE boundary...")
    before_results = send_batch("before")

    while time.time() < boundary:
        time.sleep(0.01)

    print("Sending 10 requests AFTER boundary...")
    after_results = send_batch("after")

    # Step 4: check the run is valid
    before_ids = set(r["window_id"] for r in before_results)
    after_ids = set(r["window_id"] for r in after_results)

    if before_ids != {before_window} or after_ids != {after_window}:
        print("Experiment invalid: requests crossed a window boundary.")
        print("Nothing saved. Run again.")
        raise SystemExit(1)

    # Clean start = the first count in each batch was 1
    before_clean = min(r["count"] for r in before_results) == 1
    after_clean = min(r["count"] for r in after_results) == 1

    # Step 5: save (append, one file for all runs)
    os.makedirs("results", exist_ok=True)
    write_header = not os.path.isfile(CSV_FILE) or os.path.getsize(CSV_FILE) == 0

    with open(CSV_FILE, "a", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["run_id", "timestamp", "phase", "window_id",
                        "count", "allowed", "clean_start"],
        )
        if write_header:
            writer.writeheader()

        for r in before_results + after_results:
            clean = before_clean if r["phase"] == "before" else after_clean
            writer.writerow({
                "run_id": run_id,
                "timestamp": datetime.fromtimestamp(r["timestamp"]).isoformat(
                    timespec="milliseconds"),
                "phase": r["phase"],
                "window_id": r["window_id"],
                "count": r["count"],
                "allowed": r["allowed"],
                "clean_start": clean,
            })

    print("\n--- RUN SUMMARY ---")
    print("Before: accepted", sum(r["allowed"] for r in before_results),
          "of", LIMIT, "| clean start:", before_clean)
    print("After:  accepted", sum(r["allowed"] for r in after_results),
          "of", LIMIT, "| clean start:", after_clean)
    print("Saved to", CSV_FILE)