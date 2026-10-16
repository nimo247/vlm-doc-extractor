# CPU evaluation and OCR box alignment

## Measured validation result

The saved three-epoch Qwen3-VL-2B adapter was trained on 168 pages. Its 40-page validation predictions and all reference image/label hashes were verified from the user's uploaded backups on 15 October 2026. Replaying the original predictions reproduced every reported count exactly. No model was loaded during this analysis; the 50 test pages were not supplied or evaluated.

| Custom metric, all 40 pages | OCR + eight-category rules | Saved adapter | Adapter + OCR boxes |
|---|---:|---:|---:|
| Key-field text F1 | 14.77% | 36.63% | 36.63% |
| Key-field text + IoU >= 0.5 F1 | 12.88% | 24.77% | 27.67% |
| Line-item cell text F1 | Unsupported | 46.01% | 46.01% |
| Line-item cell text + IoU >= 0.5 F1 | Unsupported | 17.18% | 29.24% |
| Complete-row text F1 | Unsupported | 17.04% | 17.04% |
| Schema-valid outputs | 40/40 | 30/40 | 30/40 |

These are development validation results, not official DocILE scores or an independent final test. The rule baseline supports only eight of the 36 key-field types and no line items. The reported full-task scores keep every gold category in the denominator. Its valid empty outputs do not imply successful extraction: it produced 57 fields across 28 documents, matching 39 fields; 12 documents had empty extractions. Baseline precision is 68.42%, recall 8.28%; adapter key-field precision is 48.26%, recall 29.51%. This is a limited starter comparator, not a comprehensive OCR extraction system.

The base VLM's raw strict-schema score is zero on these pages. All 40 outputs begin with Markdown fences; removing a complete outer fence makes three outputs valid JSON but none schema-valid. This does not establish that the base model cannot read documents. Saved base predictions should be retained for a fair, separate parser-policy comparison rather than regenerated unnecessarily.

## What the alignment does

`evidencedoc/docile_ocr.py` runs local Tesseract 3-mode page segmentation on a 2x copy of the page, then searches its word sequence for already-predicted text. Matching ignores case and whitespace only; punctuation, currency symbols, signs and digits must match. A match spans at most 40 OCR words in one block, each with confidence >= 50. Its normalized union box has 0.002 padding. Repeated identical field-type/value pairs use distinct OCR occurrences, preferring the nearest proposed center within 0.15 page units.

This function receives the prediction and OCR words, never reference labels. It preserves extracted values, field types and row groups. Standard schema serialization may materialize defaults already defined by the schema. Invalid JSON and schema-invalid predictions pass through unchanged. Every replaced box records its original coordinates and selected OCR word indices.

An OCR match provides a possible location, not proof that a field type or text value is correct. No reversed boxes are silently swapped, no unknown labels are guessed, and no missing text is invented.

On these 40 pages, 395 of the 681 accepted predicted fields/cells received OCR boxes. Grounded key-field matches rose from 94 to 105; grounded line-item matches rose from 84 to 143. All text and row counts stayed identical. The change is not uniformly beneficial: key-field grounded counts improved on 9 pages and worsened on 3; line-item counts improved on 16 and worsened on 1. Keep this optional until the frozen final test.

The initial pilot used the first three validation pages; the same alignment settings were then used on all 40. Subsequent cache-only scoring added the printed-label rule baseline without changing alignment settings. No test-based parameter selection was performed.

## Run against saved predictions

Use the existing project environment with Pillow and Pydantic. This adds no Torch, Transformers, HF download, or GPU requirement. Install the local Tesseract executable and English data if absent:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

For the original Codespaces/Kaggle data paths, run from the project root after extracting the saved evaluation outputs there:

```bash
.venv/bin/python -u -m scripts.evaluate_docile_ocr \
  --manifest data/docile_prepared/manifest.jsonl \
  --data-root . \
  --run outputs/readable-3ep-validation40-sampled-v1 \
  --output outputs/docile-cpu-comparison-v1
```

On Kaggle use `python` instead of `.venv/bin/python`. The `docile_readable/manifest.jsonl` also works because validation images and labels were preserved. The command checks the original image and label hashes before running OCR. It refuses an output folder containing previous results and restricts this development experiment to validation. Choose a new folder for another run. The cache is keyed by the image hash, Tesseract version, OCR language, scale and segmentation mode.

Outputs:

- `report.json`: original scores, OCR-aligned scores, limited rule baseline, policy, document hashes, cache count and timings.
- `aligned_predictions.jsonl`: aligned output, source boxes, OCR word indices and evaluation counts.
- `ocr_baseline_predictions.jsonl`: independent printed-label baseline predictions and scores.

The original input report, predictions, images and labels remain unchanged. OCR failures abort this comparison rather than fabricate results. This CLI is not currently a resumable VLM generation runner.

## Timing and verification

Tesseract 5.3.4 processed all 40 pages on the builder CPU. Recorded fresh per-page OCR times sum to 70.27 seconds. The 40-page alignment run took 33.70 seconds with two workers and three pilot pages already cached; the subsequent baseline comparison reused all 40 OCR cache entries. These times are hardware-dependent. They do not replace the adapter's recorded median generation time of 118.47 seconds or establish a serving speedup.

Eight unit tests passed for exact full-token matching, currency preservation, multiline matching, confidence/block boundaries, distant-value abstention, repeated-value locations, prediction immutability and baseline cue requirements. Actual 40-page runs verified that canonical field texts/types/groups and all text/row metric counts remain unchanged, invalid outputs pass through verbatim, and original metrics reproduce exactly.

The original document workspace retains its full-page output contract. The separate DocILE-specific review/API flow is now available at `/docile`, including optional alignment, original raw output, validation failures and manual review. See [application setup](DOCILE_APP.md). The live GPU-service entry point still needs a real GPU smoke test, followed by a frozen final test and deployment measurements.
