# PuzzleCodeBench

## Structure
- `construction/`: Puzzle definitions, renderers, and validation logic.
- `solver/`: Reference solver implementations for each puzzle.
- `data/`: Benchmark datasets (`init/`, `figs/`, `anchor.jsonl`, `transfer.jsonl`, `rules_and_schema.jsonl`).
- `scripts/`: Data build, dataset build, eval, and result summary scripts.
- `results/`: Model outputs, transfer-level eval results, and final aggregated metrics.

## Build Data
Use this to solve `data/init/*_init.jsonl` and generate solved init files.
```bash
python scripts/build_data.py
```

## Build Dataset
Use this to build final datasets (anchor also renders figures).
```bash
python scripts/build_dataset.py
```

## Eval Anchor
Use this to extract and rerun anchor-level model outputs.
```bash
python scripts/eval_anchor.py --input-file results/results-gemini-3.1-pro-preview.jsonl --output-dir results/anchor-level --dataset data/anchor.jsonl
```

## Eval
Use this to run transfer-level eval for reference solver or one model.
```bash
bash scripts/eval_transfer.sh ref
bash scripts/eval_transfer.sh gemini-3.1-pro-preview
```

## Print Results
Use this to merge anchor + transfer results and write final metrics.
```bash
python scripts/print_results.py
```


All Results are computed and saved in `results/`.
All Models API outputs are in `results/results-*.jsonl`.