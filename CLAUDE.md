# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Individual graded lab (VinUni Day 09, docs in Vietnamese): an automated label-QC pipeline for a YOLO dataset (224 COCO images, 4 classes `car, person, truck, bus`). The student writes **4 modules**; everything else is pre-written ("ĐÃ VIẾT SẴN") and integrity-checked. See `GUIDE.md` (workflow), `RULES.md` (constraints), `docs/PIPELINE.md` (architecture + all 22 issue codes).

## Commands

Windows has no `make`: run the python commands directly, with `PYTHONUTF8=1` set (Makefile exports it).

```bash
python -m pytest -q                                   # all tests (79). Before the 4 modules exist: 55 failed, 24 passed is expected
python -m pytest tests/test_label_format.py -q        # one module's tests
python -m pytest tests/test_gate.py -q -k <name>      # single test
python -m pipeline.run                                # full pipeline; exit 0 Release, 10 Hold, 20 Rework, 30 paused, 1 error
python -m pipeline.calibrate --sweep duplicates.phash_dist=2,4,6,8,10,12,14,16,20 --sweep second_opinion.conf=0.1,0.25,0.4,0.5,0.6,0.7,0.8 --out submission/calibration
python scripts/check_submission.py --no-train         # make check-core (drop --no-train after Colab training)
python scripts/viz_labels.py img_0001 img_0030        # draw labels -> work/viz/
```

Pipeline needs only `requirements.txt` (no torch/GPU): model predictions for `second_opinion` are cached in `data/cache/checker_preds.json`. `requirements-train.txt` (ultralytics) is only for training, normally on Colab via `notebooks/day09_train_compare.ipynb`.

## Architecture

- `pipeline/common.py`: `Issue` dataclass (check, severity `ERROR`/`WARN`, code, image stem, message, 1-based line, extra), `Dataset` (YOLO `images/` + `labels/` + `data.yaml`), `parse_yolo_line` (raises `ValueError`), `iou_xywh`. Image extensions compared lowercase (`.JPG` counts).
- `pipeline/checks/`: each module exposes `run(ds, cfg) -> list[Issue]`. Registered in `checks/__init__.py`: `INTAKE_CHECKS = [images, duplicates]` run at intake; `QC_CHECKS = [missing_labels, label_format, class_names, stats, second_opinion]` run each QC round.
- `pipeline/run.py` orchestrator: intake (copies `data/raw` to `work/run/ds/`, raw is never modified) → QC v1 → `autofix.fix` → QC v2 → `review_queue.build_queue` → simulated human review (`scripts/human_review_sim.py`, budget 80 images) → QC v3 (+ second autofix if errors remain) → `gate.decide` → `export` (skipped on Rework unless `--export-on-rework`). Reports go to `submission/reports/01_*`…`08_summary.json`; export to `submission/export/clean_v1/`.
- Gate semantics: any ERROR → Rework; else ratio of distinct *images* with warnings (excluding reviewed images, but never excluding errors) ≥ `gate.warn_ratio_hold` → Hold; else Release.
- `pipeline/calibrate.py` scores checks against `data/calib/MANIFEST.csv` (answer key) and sweeps config params.

## Student-written modules (stubs with detailed docstrings = spec)

| File | Test |
|---|---|
| `pipeline/checks/label_format.py` | `tests/test_label_format.py` |
| `pipeline/steps/gate.py` | `tests/test_gate.py` |
| `pipeline/steps/autofix.py` | `tests/test_autofix.py` |
| `pipeline/checks/second_opinion.py` | `tests/test_second_opinion.py` |

Read the module docstring first; it defines codes, severities, and config keys. Read thresholds from `cfg`, never hardcode. Tests use a fixed config in `tests/conftest.py`, independent of `configs/pipeline.yaml`.

## Hard rules (enforced by `scripts/check_submission.py` via sha1 in `scripts/_protected.json`)

- Do not edit pre-written files, `tests/`, `data/`, `scripts/human_review_sim.py`, the cache, or MANIFEST.
- In `configs/pipeline.yaml`, change **only** the two `# <-- CALIBRATE` values (`duplicates.phash_dist`, `second_opinion.conf`). Everything else is fixed.
- Check/autofix/gate code must not read `data/review_reference/`, `data/test/labels`, or `data/calib/MANIFEST.csv`, and must not hardcode image names or line numbers (static scan; graded on a renamed dataset).
- Never hand-edit generated outputs in `submission/reports/`, `submission/calibration/`, `submission/results/`.
- Never use `data/test/` for training, threshold selection, or fixing labels.
- `second_opinion` only emits warnings; `autofix` fixes only syntactic errors (never semantic labels, never invents labels for `MISSING_LABEL_FILE`).
- Honest Hold/Rework is acceptable; claiming Release or "clean beats raw" without supporting numbers is penalized.
- Don't commit `work/`, `.venv/`, `*.pt`.

## Submission

Repo name `K5-L23-DAY09-<MSHV>-AutoQCPipeline`. Change README title to `# Day 09 Lab — <Họ và tên>: <MSHV> - <Họ và tên>`, fill `submission/REPORT.md` (remove all `TODO(học viên)`), run check-core until no `LỖI`.
