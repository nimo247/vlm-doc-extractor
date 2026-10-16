# DocILE preparation and task scope

The existing full-page parser emits `Document` JSON and Markdown. DocILE fine-tuning uses a separate `docile-extraction-1.0` schema: annotated key fields with text and normalized bounding boxes, and grouped line-item fields. It preserves the upstream category names instead of forcing `document_id` to mean invoice number on every document or replacing `amount_total_gross` with `amount_due`.

The labels come directly from the supplied DocILE annotation arrays. Metadata currency, OCR predictions, and unannotated page text are not inserted into targets. This is not full-page transcription or full table reconstruction. The Markdown renderer creates an extraction summary with a field table and a line-item table. Its column headings are category names rather than transcribed document headers.

## Prepare on CPU in Codespaces

Run from the EvidenceDoc project root after downloading and unzipping `annotated-trainval` into `data/docile`:

```bash
.venv/bin/python -m scripts.prepare_docile --dataset data/docile \
  --output data/docile_prepared --train-limit 200 --validation-limit 40 --test-limit 50
.venv/bin/python -m scripts.train --config configs/docile-t4.yaml --dry-run
```

This pilot uses only the upstream `train.json`. The upstream 500-document validation split is reserved and not read for selection or targets. This pilot's own validation and test sets are drawn from the upstream training documents. Do not call its results official DocILE benchmark scores.

The builder filters to English single-page documents with at least three key fields, complete usable texts/boxes, and compact targets. It excludes documents flagged as containing an unannotated second table. All exclusions and actual selected counts are recorded in `data/docile_prepared/preparation_report.json`. Target size is a character budget, not a tokenizer-derived limit; check sequence lengths and memory on GPU before longer training. The defaults cap target JSON at 12,000 characters.

Layouts sharing a cluster ID, documents sharing an original source filename, and identical source PDF bytes are connected before splitting. Entire connected groups belong to one split. Independent groups are deterministically shuffled and assigned roughly 70/15/15 percent to train/validation/test, then document counts are capped. Actual counts may be smaller than requested. Duplicate rendered images are removed, preferring held-out copies. This protects against exact duplication, not every possible near-duplicate or upstream clustering error.

Preparation audits group/source separation, exact image hashes, record IDs, and schema validity. It records a SHA-256 for the locked test IDs/labels. Keep the same manifest for baseline and adapted evaluation; tune on validation only. Visually inspect a sample of the supplied field texts and boxes before interpreting literal-text quality metrics. Supplied labels have not been independently reviewed by this builder.

The output includes PNGs, JSON targets, manifests, a report, and a sample extraction-summary Markdown file. `outputs/evidencedoc-docile-data.zip` packages those outputs using paths relative to the project root. It does not include source PDFs or OCR files. Use `--overwrite` only when intentionally rebuilding a prepared subset; otherwise the builder refuses to overwrite an existing manifest.

## GPU training

Extract the prepared-data ZIP into the project root in Colab. Use the updated training script and `configs/docile-t4.yaml`:

```bash
python -m scripts.train --config configs/docile-t4.yaml --dry-run
python -m scripts.train --config configs/docile-t4.yaml --max-steps 2
```

Start from a new base-model LoRA adapter for the real dataset. The prior two-step synthetic adapter is only a smoke-test artifact. This task uses the previously tested T4 settings: FP16 computation, FP32 trainable adapter parameters, standard NLL, four-bit NF4, batch size one, and small image pixel budget. Real-document GPU training and generation have not yet been run by the builder. Tiny text may require a larger image budget; measure the resulting memory/quality change.

The DocILE adapter expects the DocILE task prompt and extraction schema. It is not directly interchangeable with the application's existing full-page `vlm` backend. Generation/evaluation and an application integration must use the matching prompt/schema; a task-mismatched checkpoint must not be advertised as improving full-page Markdown parsing.

## Upstream references

- Dataset and access: https://docile.rossum.ai/
- Loader, category vocabulary, and annotation API: https://github.com/rossumai/docile
- Dataset paper: https://arxiv.org/abs/2302.05658

## T4 recovery for long targets

The user completed two DocILE training steps and all 40 validation forwards on a
Tesla T4 with 131072 pixels and activation offloading. Peak PyTorch allocated
memory was 14849033216 bytes. The unbounded one-epoch run subsequently exhausted
GPU memory after six optimizer steps. This is not a completed model-quality run.

For a bounded training subset, run from the project root with the training
dependencies installed:

```bash
python -u -m scripts.prepare_t4_training --config configs/docile-t4.yaml --max-tokens 3072 --run
```

The helper counts full chat sequences through the actual processor, including
expanded image tokens and the complete assistant JSON. It drops whole overlong
training records without editing labels or truncating sequences. Validation and
test records and their gold label bytes are fingerprinted and preserved.
`data/docile_t4/length_report.json` records the original and retained counts,
excluded IDs, measured lengths and held-out hashes. Training counts therefore
may be smaller than 200; report the actual bounded audit count.

Before starting one epoch, the helper trains on up to eight longest retained
examples with evaluation disabled. It stops if this check fails. It then starts
fresh adapters for the bounded full run, evaluates the unchanged validation set
at epoch end and saves every five steps. This GPU workflow has not been executed
by the project builder. CPU tests verify selection and held-out integrity;
successful GPU execution must be checked in the user's Colab session.

The original preparation files remain intact. This length-filtered training
subset is not an official DocILE benchmark. It does not establish held-out
extraction accuracy; base-versus-adapter inference evaluation remains required.

## User-reported full run and paired inference

The bounded workflow subsequently completed in the user's Colab: 102 retained
training documents (98 excluded for length), 26 optimizer steps, one epoch, and
all 40 unchanged validation documents. Reported validation loss was 0.8465 and
teacher-forced token accuracy 0.6989. These are not extraction accuracy scores.
The 50 test documents remain reserved. The user reported completion; model
weights have not been provided to the builder.

First back up the final adapter and its processor/config/report files, then
check actual generation on three validation documents:

```bash
python -u -m scripts.evaluate_docile \
  --adapter checkpoints/docile-t4-bounded-3072-full \
  --split validation --limit 3 --max-new-tokens 8192 \
  --output outputs/docile-validation-preview
```

This loads one base model in NF4, generates base outputs, then loads the saved
adapter into that same base and generates on the identical images. It uses the
DocILE training prompt/instruction, processor and pixel budget for both. Labels
are used only for scoring, never inserted into the generation prompt.
Predictions are written and flushed after every document, including raw text,
schema validity, generation errors, token-limit flags, elapsed time and counts.
The report records paired document/image/gold hashes and evaluation settings.

Custom micro precision/recall/F1 compare field type and whitespace/case-normalized
exact text. A second metric also requires normalized bounding-box IoU >= 0.5
with maximum one-to-one matching. Line-item cell scores ignore row groups; a
separate complete-row metric requires the full multiset of cell types/text in
the row. Invalid outputs count all gold fields as missed; repeated predictions
cannot inflate recall. Undefined precision/recall/F1 are null, not invented
perfect scores. Unmatched values are not independently verified hallucinations.

These are custom extraction metrics, not official DocILE PCC-based AP/F1. A
three-document validation preview is only a pipeline check. After settings are
fixed, use `--split test --limit 0` and a separate output directory for the same
locked 50 documents. Do not advertise test quality from validation previews.
The builder executed four CPU metric/prompt checks and verified CLI help; GPU
generation has not been executed here. First-generation latency includes cold
start effects and is not a standardized serving benchmark.

