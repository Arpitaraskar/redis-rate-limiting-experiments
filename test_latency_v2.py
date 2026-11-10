import redis
import time
import csv
import os
import random
import statistics
from datetime import datetime

# Redis configuration
client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

# Experiment configuration (same as the first latency test)
BUCKET_CAPACITY = 2000
REFILL_RATE = 10 / 60

FIXED_WINDOW_LIMIT = 5000
WINDOW_SIZE = 60

WARMUP_REQUESTS = 100
TOTAL_REQUESTS = 1000

# New in this version
TRIALS = 30
PAUSE_SECONDS = 0.5   # short pause between algorithms

RAW_FILE = os.path.join("results", "latency_v2_raw.csv")
TRIAL_FILE = os.path.join("results", "latency_v2_trials.csv")

# Separate keys for latency experiments
FIXED_KEY = "research:latency:fixed_window"
NON_ATOMIC_KEY = "research:latency:non_atomic"
ATOMIC_KEY = "research:latency:atomic"

# Load Fixed Window Lua script
with open("fixed_window.lua", "r") as file:
    fixed_window_script = file.read()

fixed_window = client.register_script(fixed_window_script)

# Load Atomic Token Bucket Lua script
with open("atomic_token_bucket.lua", "r") as file:
    atomic_script = file.read()

atomic_token_bucket = client.register_script(atomic_script)


def send_fixed_window_request():
    result = fixed_window(
        keys=[FIXED_KEY],
        args=[FIXED_WINDOW_LIMIT, WINDOW_SIZE]
    )

    return int(result[1])


def send_non_atomic_request():
    bucket = client.hgetall(NON_ATOMIC_KEY)

    current_time = time.time()

    tokens = float(bucket["tokens"])
    last_refill = float(bucket["last_refill"])

    elapsed_time = current_time - last_refill
    refilled_tokens = elapsed_time * REFILL_RATE

    new_tokens = min(
        BUCKET_CAPACITY,
        tokens + refilled_tokens
    )

    allowed = False

    if new_tokens >= 1:
        new_tokens -= 1
        allowed = True

    client.hset(
        NON_ATOMIC_KEY,
        mapping={
            "tokens": new_tokens,
            "last_refill": current_time
        }
    )

    return int(allowed)


def send_atomic_request():
    result = atomic_token_bucket(
        keys=[ATOMIC_KEY],
        args=[
            BUCKET_CAPACITY,
            REFILL_RATE
        ]
    )

    return int(result[0])


def measure_latency(request_function, total_requests):

    latencies = []

    for _ in range(total_requests):

        start_time = time.perf_counter()

        request_function()

        end_time = time.perf_counter()

        latencies.append((end_time - start_time) * 1000)

    return latencies


def reset_experiment_state():

    client.delete(FIXED_KEY, NON_ATOMIC_KEY, ATOMIC_KEY)

    current_time = time.time()

    client.hset(
        NON_ATOMIC_KEY,
        mapping={
            "tokens": BUCKET_CAPACITY,
            "last_refill": current_time
        }
    )

    client.hset(
        ATOMIC_KEY,
        mapping={
            "tokens": BUCKET_CAPACITY,
            "last_refill": current_time
        }
    )


def calculate_statistics(latencies):

    return {
        "mean_ms": statistics.mean(latencies),
        "median_ms": statistics.median(latencies),
        "p95_ms": statistics.quantiles(latencies, n=100)[94],
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "std_dev_ms": statistics.stdev(latencies)
    }


def run_latency_test(request_function):

    # Start with clean Redis state
    reset_experiment_state()

    # Warm-up requests
    for _ in range(WARMUP_REQUESTS):
        request_function()

    # Reset again before actual measurement
    reset_experiment_state()

    latencies = measure_latency(request_function, TOTAL_REQUESTS)

    return latencies, calculate_statistics(latencies)


def open_csv(path, fieldnames):
    os.makedirs("results", exist_ok=True)
    write_header = not os.path.isfile(path) or os.path.getsize(path) == 0

    file = open(path, "a", newline="")
    writer = csv.DictWriter(file, fieldnames=fieldnames)

    if write_header:
        writer.writeheader()

    return file, writer


if __name__ == "__main__":

    print("Redis connected:", client.ping())

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    print("Run ID:", run_id)
    print("Trials:", TRIALS, "| requests per algorithm:", TOTAL_REQUESTS)

    algorithms = [
        ("Fixed Window", send_fixed_window_request),
        ("Non-atomic Token Bucket", send_non_atomic_request),
        ("Atomic Token Bucket", send_atomic_request)
    ]

    raw_file, raw_writer = open_csv(
        RAW_FILE,
        ["run_id", "trial", "position", "algorithm",
         "request_index", "latency_ms"]
    )

    trial_file, trial_writer = open_csv(
        TRIAL_FILE,
        ["run_id", "trial", "position", "algorithm", "mean_ms",
         "median_ms", "p95_ms", "min_ms", "max_ms", "std_dev_ms"]
    )

    for trial in range(1, TRIALS + 1):

        # Random order in every trial
        order = algorithms[:]
        random.shuffle(order)

        print(f"\nTrial {trial} order:", " -> ".join(name for name, _ in order))

        for position, (name, request_function) in enumerate(order, start=1):

            latencies, stats = run_latency_test(request_function)

            print(f"  {name}: mean {stats['mean_ms']:.3f} ms | "
                  f"p95 {stats['p95_ms']:.3f} ms")

            for index, value in enumerate(latencies, start=1):
                raw_writer.writerow({
                    "run_id": run_id,
                    "trial": trial,
                    "position": position,
                    "algorithm": name,
                    "request_index": index,
                    "latency_ms": round(value, 6)
                })

            trial_writer.writerow({
                "run_id": run_id,
                "trial": trial,
                "position": position,
                "algorithm": name,
                **{key: round(value, 6) for key, value in stats.items()}
            })

            time.sleep(PAUSE_SECONDS)

        raw_file.flush()
        trial_file.flush()

    raw_file.close()
    trial_file.close()
    client.close()

    print("\nLatency experiment completed!")
    print("Saved to", TRIAL_FILE, "and", RAW_FILE)