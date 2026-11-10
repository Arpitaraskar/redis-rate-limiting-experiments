import redis
import time
import csv
import os
import statistics
from datetime import datetime

# Redis configuration
client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

# Experiment configuration
BUCKET_CAPACITY = 2000
REFILL_RATE = 10 / 60

FIXED_WINDOW_LIMIT = 5000
WINDOW_SIZE = 60

WARMUP_REQUESTS = 100
TOTAL_REQUESTS = 1000

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

        latency_ms = (end_time - start_time) * 1000

        latencies.append(latency_ms)

    return latencies

def reset_experiment_state():

    # Clear previous latency-test data
    client.delete(
        FIXED_KEY,
        NON_ATOMIC_KEY,
        ATOMIC_KEY
    )

    current_time = time.time()

    # Initialize Non-atomic Token Bucket
    client.hset(
        NON_ATOMIC_KEY,
        mapping={
            "tokens": BUCKET_CAPACITY,
            "last_refill": current_time
        }
    )

    # Initialize Atomic Token Bucket
    client.hset(
        ATOMIC_KEY,
        mapping={
            "tokens": BUCKET_CAPACITY,
            "last_refill": current_time
        }
    )

    print("Redis state initialized successfully.")

def calculate_statistics(latencies):

    return {
        "mean_ms": statistics.mean(latencies),
        "median_ms": statistics.median(latencies),
        "p95_ms": statistics.quantiles(
            latencies, n=100
        )[94],
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "std_dev_ms": statistics.stdev(latencies)
    }

def run_latency_test(name, request_function):

    print(f"\nTesting {name}...")

    # Start with clean Redis state
    reset_experiment_state()

    # Warm-up requests
    for _ in range(WARMUP_REQUESTS):
        request_function()

    # Reset again before actual measurement
    reset_experiment_state()

    # Measure requests
    latencies = measure_latency(
        request_function,
        TOTAL_REQUESTS
    )

    stats = calculate_statistics(latencies)

    print(f"{name} results:")
    for metric, value in stats.items():
        print(f"{metric}: {value:.4f}")

    return latencies, stats

def save_results(all_stats):

    os.makedirs("results", exist_ok=True)

    file_path = "results/latency_results.csv"

    with open(file_path, "w", newline="") as file:
        fieldnames = [
            "algorithm",
            "mean_ms",
            "median_ms",
            "p95_ms",
            "min_ms",
            "max_ms",
            "std_dev_ms"
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for algorithm, stats in all_stats.items():
            row = {
                "algorithm": algorithm,
                **stats
            }
            writer.writerow(row)

    print(f"\nResults saved to {file_path}")


if __name__ == "__main__":

    print("Redis connected:", client.ping())
    print("Starting latency comparison...")

    all_stats = {}

    algorithms = [
        ("Fixed Window", send_fixed_window_request),
        ("Non-atomic Token Bucket", send_non_atomic_request),
        ("Atomic Token Bucket", send_atomic_request)
    ]

    for name, request_function in algorithms:

        latencies, stats = run_latency_test(
            name,
            request_function
        )

        all_stats[name] = stats

    save_results(all_stats)

    client.close()

    print("\nLatency experiment completed!")