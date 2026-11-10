
import csv
from pathlib import Path
from collections import defaultdict
from statistics import mean

RESULTS_DIR = Path("results")

metrics = [
    "mean_ms",
    "median_ms",
    "p95_ms",
    "min_ms",
    "max_ms",
    "std_dev_ms"
]

# Store values separately for each algorithm and metric
data = defaultdict(lambda: defaultdict(list))

# Read all five trial files
for trial_number in range(1, 6):
    file_path = RESULTS_DIR / f"latency_trial{trial_number}.csv"

    with open(file_path, "r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            algorithm = row["algorithm"]

            for metric in metrics:
                data[algorithm][metric].append(float(row[metric]))

# Calculate average across five trials
output_rows = []

for algorithm, values in data.items():
    result = {"algorithm": algorithm, "trials": 5}

    for metric in metrics:
        result[f"avg_{metric}"] = mean(values[metric])

    output_rows.append(result)

# Save summary
output_file = RESULTS_DIR / "latency_summary.csv"

with open(output_file, "w", newline="") as file:
    fieldnames = ["algorithm", "trials"] + [
        f"avg_{metric}" for metric in metrics
    ]

    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)

print("Latency analysis completed!")
print(f"Summary saved to: {output_file}")

for row in output_rows:
    print(f"\n{row['algorithm']}")
    print(f"Average mean latency: {row['avg_mean_ms']:.4f} ms")
    print(f"Average p95 latency: {row['avg_p95_ms']:.4f} ms")
