# EvidenceDoc

A small vision-language model fine-tuned for invoice key fields, bounding boxes and grouped line items, with a browser workspace for inspecting results and failures.

**Current status:** training, 40-page validation and the frozen 50-page test are complete. On the custom test subset, the adapter achieved 34.88% key-field text F1, 33.66% line-item cell text F1 and 70% schema validity. The user demonstrated a fresh PDF upload through the Codespaces UI, authenticated Kaggle T4 service and review/export interface. Substantial semantic and localization errors remain; this is an evaluated prototype.

## Implemented

- Qwen/Qwen3-VL-2B-Instruct, 4-bit NF4, rank-8 LoRA: 8,716,288 trainable parameters, about 0.408% of all parameters.
- Custom DocILE subset: 168 training pages, 40 validation pages, 50 locked test pages; group/source-separated splits derived from official training data. This is not the official DocILE benchmark.
- Training on one Tesla T4: approximately 69 minutes and 6.6 GiB peak PyTorch allocated memory, recorded in the user's run.
- Explicit image-resolution handling, complete-example filtering, assistant-only loss and supervised end-of-turn tokens.
- Strict schema checks; field/cell text F1, one-to-one box matching at IoU >= 0.5 and complete-row metrics. Invalid outputs count as misses.
- Eight-category Tesseract/rules baseline and optional OCR box alignment, preserving field text, types, row groups and original raw output.
- FastAPI UI, source-region overlays, manual JSON review, JSON/Markdown exports, authenticated GPU service and short-request job polling.
- Resumable evaluation with per-page disk saves, downloadable progress snapshots and refusal to mix changed data/model/configuration settings.

The live adapter receives a page image and generates extraction JSON. Tesseract is a separate backend or optional alignment stage. Native-PDF semantic evidence checks are proposed future work. The demonstrated GPU service uses Transformers/PEFT; vLLM performance has not been established.

## Final test results

Micro F1 on all 50 original locked test pages, evaluated once with the completed adapter and existing OCR policy. Failed outputs remain in the denominator. These are custom subset scores, not official DocILE scores.

| Metric | OCR/rules (eight categories) | Adapter | Adapter + OCR boxes |
|---|---:|---:|---:|
| Key-field text | 7.36% | 34.88% | 34.88% |
| Key-field text + box | 7.02% | 24.10% | 28.12% |
| Line-item cell text | Unsupported | 33.66% | 33.66% |
| Line-item cell text + box | Unsupported | 15.74% | 23.00% |
| Complete-row text | Unsupported | 9.95% | 9.95% |

The adapter returned valid JSON on 40/50 pages and schema-valid output on 35/50. Eight generations hit the 4,096-token cap; no execution errors occurred. OCR alignment changed 364 boxes without changing text, field types or row groups. The partial OCR baseline covers eight categories and no line items; all gold categories remain in its denominator.

Tesla T4 adapter generation took 153.0 minutes in total, with a median of 117.8 seconds/page and p95 of 435.8 seconds/page. Peak PyTorch allocated memory was 2.36 GiB; this excludes reserved memory and is not total GPU usage. The CPU OCR comparison added 47.3 seconds of wall time. No base-model test score is claimed.

See [the final report](docs/DOCILE_FINAL_RESULTS.md), [recorded aggregate results](benchmarks/docile-final-test/final_summary.json) and [verification scope](validation/DOCILE_FINAL_RESULTS_VERIFICATION.json). Final evaluation used Transformers 5.16.1 and PEFT 0.20.0; validation used 5.18.0 and 0.21.1, so cross-split changes are not a controlled software-version comparison.

## Measured validation results

Micro F1 on the same 40 validation pages. Development choices were made on validation; these are not untouched test scores.

| Metric | OCR/rules | Adapter | Adapter + OCR boxes |
|---|---:|---:|---:|
| Key-field text | 14.77% | 36.63% | 36.63% |
| Key-field text + box | 12.88% | 24.77% | 27.67% |
| Line-item cell text | Unsupported | 46.01% | 46.01% |
| Line-item cell text + box | Unsupported | 17.18% | 29.24% |
| Complete-row text | Unsupported | 17.04% | 17.04% |

OCR rules cover eight field categories and no line items; all gold categories remain in the denominator. Thirty of 40 adapter outputs passed the schema. The base VLM had 0/40 accepted outputs under the same strict task prompt/parser; this exposes format/schema failures and does not establish zero reading ability or superiority to stronger AI systems.

Recorded adapter generation latency had a median of 118.5 seconds and a maximum of 465.1 seconds. A user-reported API smoke test generated 719 tokens in 79.1 seconds with about 2.30 GiB peak PyTorch allocated memory. A separate fresh restaurant-invoice upload took about 2.2 minutes and confused quantities and addresses. Schema validity is not semantic correctness.

## Run the application

Install the application with `python -m pip install -e .`, restore the evaluation/review backups with `python -m scripts.restore_docile_review`, then start `python -m uvicorn evidencedoc.app:app --host 127.0.0.1 --port 8000` and open `/docile`.

The final evaluation has already completed. These commands document reproduction or recovery on a compatible Kaggle GPU environment; another long GPU run is not needed to view the saved results:

```bash
python -m scripts.finalize_docile --prepare-only
python -u -m scripts.finalize_docile
```

The runner restores original data from attached Input folders, checks the registered test fingerprint and adapter hash, evaluates only the adapter on the 50 test pages, and applies the existing CPU OCR/alignment policy. Base versus adapter remains a validation-only comparison. Resume requires retained result files and identical settings. Source archives omit model weights, real document data and predictions.

- [Application and live connection](docs/DOCILE_APP.md)
- [Measured OCR comparison](docs/DOCILE_OCR_ALIGNMENT.md)
- [Final results and limitations](docs/DOCILE_FINAL_RESULTS.md)
- [Reproduction, interruption recovery and demo handoff](docs/DOCILE_FINALIZE.md)
- [Resume project entry](docs/EVIDENCEDOC_RESUME.tex)
- [Earlier general document workspace](docs/LEGACY_DOCUMENT_WORKSPACE.md)

Tests: `python -m pip install -e '.[dev]'` followed by `python -m pytest -q`.

Scope: single-page English key-field and line-item extraction. Full-page transcription, handwriting, multi-page linking, durable production queues and reliable semantic verification are outside the demonstrated capability. Keep the forwarded review app private; it has no user accounts. No official DocILE score or production reliability claim is made.

Project code and generated samples are MIT licensed. External tools, models and datasets retain their own licenses.
