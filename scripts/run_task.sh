set -euo pipefail

# Ensure project root is on PYTHONPATH
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"

# Activate your venv
source .venv/bin/activate


ver="taskA-v1" # @20251029: v1.0
ver="taskA-v2" # @20251030: fix a bug

rep=1
seed=$(date +%s)
num_samples=100
dataset="email_train.csv"

for rep in {1..3}; do
  python exps/exp.py \
    -v "$ver" \
    -r "$rep" \
    -s "$seed" \
    -n "$num_samples" \
    -m "mean" \
    -d "$dataset"

  python exps/exp.py \
    -v "$ver" \
    -r "$rep" \
    -s "$seed" \
    -n "$num_samples" \
    -m "sum" \
    -d "$dataset"
done
