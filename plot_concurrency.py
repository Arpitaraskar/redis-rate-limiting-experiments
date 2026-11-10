
import pandas as pd
import matplotlib.pyplot as plt

# Read non-atomic Token Bucket results (CSV has no header)
non_atomic = pd.read_csv(
    "results/non_atomic_results.csv",
    header=None,
    names=[
        "timestamp",
        "total_requests",
        "workers",
        "allowed",
        "rejected",
        "duration"
    ]
)

# Read atomic Token Bucket results (CSV has a header)
atomic = pd.read_csv("results/atomic_results.csv")

# Calculate average accepted requests across all trials
non_atomic_avg = non_atomic["allowed"].mean()
atomic_avg = atomic["allowed"].mean()

# Prepare graph data
algorithms = ["Non-atomic Token Bucket", "Atomic Token Bucket (Lua)"]
averages = [non_atomic_avg, atomic_avg]

# Create bar graph
plt.figure(figsize=(9, 5))
bars = plt.bar(algorithms, averages)

plt.title("Token Bucket Concurrency Comparison")
plt.xlabel("Rate Limiting Algorithm")
plt.ylabel("Average Accepted Requests (out of 50)")
plt.ylim(0, 50)

# Display values above bars
for bar, value in zip(bars, averages):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.5,
        f"{value:.2f}",
        ha="center"
    )

plt.figtext(
    0.5, 0.01,
    "50 concurrent requests per trial; 25 trials per implementation.",
    ha="center",
    fontsize=9
)

plt.tight_layout(rect=[0, 0.05, 1, 1])

# Save graph
plt.savefig(
    "results/token_bucket_concurrency_comparison.png",
    dpi=300
)

plt.show()

print("Non-atomic average accepted:", round(non_atomic_avg, 2))
print("Atomic average accepted:", round(atomic_avg, 2))
print("Figure 3 saved successfully.")
