## Student Project Template

This template mirrors the structure of `example-project` with a clean separation between `algs` (core algorithms) and `exps` (experiments). 
The workflow is: 

1. scripts → exps/exp.py → algs, with results logged to `logs/mylog.txt` as JSON lines. 
2. `vis.ipynb` visualizes results by reading `logs/mylog.txt`.


### Setup

Run the following commands to set up the Python environment.

```bash
uv init
uv run main.py
```


### Run an experiment

```bash
bash scripts/run_task.sh
```

Each run appends a single JSON object per line to `logs/mylog.txt`.


### Visualize

Open `vis.ipynb` and run the cells to read `logs/mylog.txt` and plot results.


### Testing

```bash
source .venv/bin/activate
py.test -s -vv
```
