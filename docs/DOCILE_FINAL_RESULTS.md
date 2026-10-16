# EvidenceDoc: completed experiment

Training and the frozen final evaluation are complete as of 16 October 2026. EvidenceDoc is a small VLM adaptation and evaluation project with a working review interface. The measured accuracy supports a research/engineering prototype, not autonomous invoice processing.

## What the system does

A rendered document page is passed directly to Qwen3-VL-2B-Instruct with a trained LoRA adapter. It generates JSON containing invoice field categories, verbatim text, normalized page coordinates and grouped line-item cells. Pydantic validates structural and field-category rules. The review UI shows source-region overlays, manual edits and JSON/Markdown exports. An authenticated FastAPI service runs the model on a Kaggle T4; asynchronous job polling keeps browser requests short.

The project does not train OCR from scratch. The base VLM already has text-reading ability. Tesseract is an independent rules baseline and an optional postprocessing stage that aligns predicted strings to OCR boxes. Schema validation does not prove that a field value, category, row or box is correct. Native-PDF semantic verification and vLLM serving are not implemented capabilities of this release.

## Data and training

- Custom English, single-page, length-filtered DocILE subset derived from the official training data, rather than the official test benchmark.
- 168 retained training pages, 40 development/validation pages and 50 original locked test pages. The Kaggle audit reported unique IDs, group/source isolation, image-hash checks and valid schema/evidence references. The runner verified the original registered test fingerprint before inference.
- Base model: `Qwen/Qwen3-VL-2B-Instruct`; rank-8 LoRA, alpha 16, 4-bit NF4. Trainable parameters: 8,716,288, about 0.408% of all parameters.
- Three epochs, batch size 1, gradient accumulation 4, 4,096-token complete-example budget, assistant-only loss with supervised end-of-turn. Images preserve readable prepared resolution, aligned to 32 pixels, with processor resizing disabled.
- Training on one T4 took 4,161.7 seconds (69.4 minutes), with 7,067,700,224 bytes (6.58 GiB) peak PyTorch allocated memory, as recorded in the trained backup.
- Completed adapter SHA256: `f0b44027a8727df30e4aafb0595973c4cfc3562bbe57e778c7288affefbf5265`.

## Frozen test method

All 50 selected pages were evaluated with the completed adapter. Maximum generation was 4,096 new tokens, sampling temperature 0.7, top-p 0.8, top-k 20, repetition penalty 1.05 and seed 42 plus the one-based document index. The recorded runtime used Tesla T4, FP16 computation and NF4 weights. No base-model test run was performed.

Text scoring matches field type plus case/whitespace-normalized exact text, retaining repeated occurrences. Grounded scoring additionally requires bounding-box IoU at least 0.5 with maximum one-to-one matching. A complete row must match the multiset of all field-type/text cells; row order is ignored. Invalid whole outputs contribute no accepted predictions and all their gold fields count as missed. This failure policy is accompanied by explicit validity rates.

The existing OCR policy was frozen before test evaluation. Tesseract uses English, PSM 3, scale 2, confidence at least 50, case/whitespace-only string matching, box padding 0.002 and a maximum center distance of 0.15. Alignment preserves predicted text, categories and row groups, and leaves invalid raw outputs unchanged. The rules baseline supports eight key-field categories and no line items; all gold categories remain in its denominator. It is a limited comparator, not a strong general-purpose document extraction baseline.

## Test results

All values below are percentages of micro F1, not percentage of documents extracted correctly.

| Metric | OCR/rules | Adapter | Adapter + OCR boxes |
|---|---:|---:|---:|
| Key-field text | 7.36 | 34.88 | 34.88 |
| Key-field text + IoU50 | 7.02 | 24.10 | 28.12 |
| Line-item cell text | Unsupported | 33.66 | 33.66 |
| Line-item cell text + IoU50 | Unsupported | 15.74 | 23.00 |
| Complete-row text | Unsupported | 9.95 | 9.95 |

| Output measure | Adapter |
|---|---:|
| Completed pages | 50/50 |
| Valid JSON | 40/50 (80%) |
| Schema-valid JSON | 35/50 (70%) |
| Invalid JSON | 10/50 |
| Valid JSON failing schema | 5/50 |
| Output token cap reached | 8/50 |
| Execution errors | 0/50 |

Token-cap hits overlap other failure categories and must not be added to them. Zero execution errors means that inference ran, not that extraction was correct.

There were 557 annotated key fields, 547 line-item cells and 142 rows. The adapter matched 165 key-field texts out of 389 accepted predictions and 139 cell texts out of 279. Grounded matches improved from 114 to 133 for key fields and from 65 to 95 for line-item cells after 364 boxes changed. Text and row scores stayed identical. The grounded improvements are 4.02 and 7.26 percentage points of F1, respectively. Complete-row matches were only 11 out of 142 gold rows, indicating substantial remaining row/cell errors.

## Timing and memory

| Measurement | Final recorded value |
|---|---:|
| Adapter generation sum, 50 pages | 9,181.6 seconds / 153.0 minutes |
| Median generation time | 117.8 seconds/page |
| p95, nearest rank | 435.8 seconds/page |
| Peak PyTorch allocated GPU memory | 2,539,125,248 bytes / 2.36 GiB |
| CPU OCR comparison wall time | 47.3 seconds |

These are recorded per-document generation timings with preprocessing/cold effects, not a standardized concurrent server benchmark. Peak allocated memory excludes allocator reservation and non-PyTorch usage. The CPU comparison runs after generation; it does not make VLM inference faster. The model's minutes-long latency limits interactive use.

## Validation context and interpretation

Earlier 40-page validation results were 36.63% key-field text F1, 46.01% line-item cell text F1 and 75% schema validity. The base VLM had 0/40 schema-accepted outputs under this task's strict prompt/parser; this demonstrates format failures, not zero OCR ability or superiority to general AI. Development decisions were made on validation. The test set was used only for the frozen final run.

Validation used Transformers 5.18.0 / PEFT 0.21.1; final inference used Transformers 5.16.1 / PEFT 0.20.0. The checkpoint and recipe fingerprints match, but the software difference means validation-versus-test changes cannot be attributed solely to the dataset split. No controlled software-version ablation is claimed.

Final versions: Torch 2.11.0+cu128, Transformers 5.16.1, PEFT 0.20.0, Accelerate 1.14.0, bitsandbytes 0.50.2 and Tesseract 5.3.4. Base-model revision: `89644892e4d85e24eaac8bacfd4f463576704203`.

## Verification and limits

The uploaded results archive passed ZIP integrity checks. Local verification confirmed 50 unique IDs and matching order/fingerprints across all journals and reports, reparsed strict JSON/schema validity, checked prediction counts, recomputed aggregate precision/recall/F1 from recorded per-page match counts, recomputed timing/memory, verified that OCR changes only boxes, and matched adapter/processor hashes to the trained backup. The 50 test IDs do not overlap the 40 validation IDs. Metric and frozen OCR-policy hashes match the source. See `validation/DOCILE_FINAL_RESULTS_VERIFICATION.json`.

The results archive does not contain the original test images or gold labels. Consequently, this local review cannot independently rerun gold matching, inspect test images, reproduce full group/source isolation or reconstruct the original dataset fingerprint; those checks were executed and reported by the Kaggle runner. No GPU generation was repeated here.

The useful project contribution is reproducible VLM adaptation under constrained GPU memory, audited splitting, explicit failure scoring, localization analysis, a controlled box-alignment comparison, and an inspectable service/UI. The remaining weaknesses include low recall, wrong categories, repetitive/incomplete output, inaccurate boxes and incorrect row grouping. Unmatched predictions are not independently verified hallucinations. This small custom benchmark does not establish generalization to all invoices, handwriting or multi-page documents.

Keep this recipe frozen after viewing the test results. Further tuning needs a new development experiment and separate untouched evaluation data.

## Handoff

1. Keep `EvidenceDoc-evaluated-backup.zip` (trained adapter), `EvidenceDoc-final-results.zip` (raw evaluation evidence) and the original prepared data backup.
2. Commit this source release, its benchmark summaries and report to the repository; do not commit dataset pages, private invoices, access keys or weights unintentionally.
3. Record a two-minute demo using a saved validation result plus a completed live upload, showing both a correct field and a failure. Show elapsed inference time honestly and explain manual review.
4. Use `docs/EVIDENCEDOC_RESUME.tex` for the measured project entry. No more training or long evaluation is required for this release.
