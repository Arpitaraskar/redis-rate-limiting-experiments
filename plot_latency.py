
import csv
import matplotlib.pyplot as plt
from pathlib import Path

RESULTS_DIR = Path("results")

# Read the summary CSV
with open(RESULTS_DIR / "latency_summary.csv", "r") as file:
    rows = list(csv.DictReader(file))

algorithms = [row["algorithm"] for row in rows]

# Extract average mean and p95 latency
mean_values = [float(row["avg_mean_ms"]) for row in rows]
p95_values = [float(row["avg_p95_ms"]) for row in rows]


# Graph 1: Mean latency
plt.figure(figsize=(9, 5))
plt.bar(algorithms, mean_values)

plt.title("Average Mean Latency Comparison")
plt.xlabel("Rate Limiting Algorithm")
plt.ylabel("Mean Latency (ms)")
plt.xticks(rotation=10)
plt.tight_layout()

plt.savefig(RESULTS_DIR / "mean_latency_comparison.png", dpi=300)
plt.show()


# Graph 2: P95 latency
plt.figure(figsize=(9, 5))
plt.bar(algorithms, p95_values)

plt.title("Average P95 Latency Comparison")
plt.xlabel("Rate Limiting Algorithm")
plt.ylabel("P95 Latency (ms)")
plt.xticks(rotation=10)
plt.tight_layout()

plt.savefig(RESULTS_DIR / "p95_latency_comparison.png", dpi=300)
plt.show()

print("Both latency graphs saved successfully!")
