import argparse
import datetime as dt
import json
import os
import sys
import time
import fcntl
import numpy as np
from typing import Any, Dict

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from algs.core import compute_sum, compute_mean  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run simple experiment that calls algs and logs JSON lines.")
    parser.add_argument("-v", "--ver", required=True, help="Experiment version tag")
    parser.add_argument("-r", "--rep", type=int, default=1, help="The r-th repetition")
    parser.add_argument("-s", "--seed", type=int, default=42, help="Base random seed")
    parser.add_argument("-d", "--dataset", default="email_train.csv", help="Dataset file name")
    parser.add_argument("-n", "--num-samples", type=int, default=100, help="Number of random samples")
    parser.add_argument(
        "-m",
        "--method",
        choices=["sum", "mean"],
        help="Which metric to compute",
    )
    parser.add_argument("-l", "--log-file", default="logs/mylog.txt", help="Path to JSONL log file")
    args = parser.parse_args()

    # Fix random seed
    np.random.seed(args.seed)

    # Prepare data
    samples = np.random.random(args.num_samples)

    # Go and run
    start_time = time.process_time()

    value = None
    if args.method == "sum":
        value = compute_sum(samples)
    if args.method == "mean":
        value = compute_mean(samples)

    runtime = time.process_time() - start_time
    
    # Post-processing if there is any
    pass

    # Log the results
    summary = {
        "ver": args.ver,
        "rep": args.rep,
        "seed": args.seed,
        "method": args.method,
        "dataset": args.dataset,
        "value": value,
        "runtime": runtime,
        "timestamp": dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    summary_text = json.dumps(summary, ensure_ascii=False)
    write_to_log_file(args.log_file, summary_text)
    print(summary_text)


def write_to_log_file(filename, logtext):
    """
    Write log entry to file with file locking to prevent simultaneous writes.
    
    Args:
        filename: Path to the log file
        logtext: Log text to write
    """
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Format the log entry with timestamp
    formatted_log = f"{logtext}\n"
    
    # Write to file with exclusive lock
    with open(filename, 'a') as f:
        try:
            # Acquire exclusive lock
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(formatted_log)
            f.flush()
        finally:
            # Release lock (automatically released when file is closed)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    main()
