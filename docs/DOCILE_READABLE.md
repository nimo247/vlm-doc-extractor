# Readable DocILE training recipe

Status: CPU helper tests pass. Full preflight on the owner's 200 training documents, GPU memory checks,
and extraction quality for this recipe have not been measured by the builder. There is no new trained adapter in this archive.

The owner reported that both base and previous adapter read the correct invoice identifier, date, and amount
on one validation image at 1280x992, while both failed at 384x288. A processor attribute change initially had
no effect; explicit `images_kwargs={"do_resize": False}` with a grid check produced the requested resolution.
At higher resolution, both still failed full extraction under the original and shorter prompts, reaching the
generation budget with incorrect categories/repetition. These observations support changing the training
recipe; they do not establish general extraction accuracy or a single cause of the remaining failures.

## What changes

- Prepared images keep their original resolution (maximum edge 1280 from the builder), aligned to 32 pixels.
  The processor receives an explicit resize override and its actual image grid is checked.
- Text, categories, row groups, and canonical gold files are preserved. Only the serialized assistant targets
  use outward coordinate quantization to 0.001. This slightly expands boxes and avoids collapsing thin boxes.
- Training and inference share one explicit compact prompt. New configs include its hash.
- A custom batch-size-one collator masks the complete prompt and supervises the full answer, including
  `<|im_end|>`. Prefix identity, stop supervision, actual image size, and complete sequence length are checked.
  This does not prove that missing stop supervision caused the previous checkpoint's repetition.
- Only whole overlong training examples are excluded. Validation and test rows/gold are fingerprinted unchanged.
- The initial GPU phase uses the eight longest eligible training examples. A separate four-document learning
  pilot is a memorization diagnostic, not a held-out result. Original checkpoints have different directories.

## CPU preflight (run first)

From the project directory, with torch, transformers 5.18.0, and base project dependencies installed:

```bash
python -u -m scripts.prepare_readable_docile --max-tokens 4096
```

This loads the processor/tokenizer only, not model weights. It audits the full original prepared manifest,
counts each complete training sequence using the same collator as training, checks actual image dimensions
and supervised stop tokens, and writes `data/docile_readable/preflight.json` plus full/stress/pilot manifests.
It writes matching configs under `configs/docile-readable-4096-*.yaml`. GPU memory suitability remains untested.

## GPU steps, after reviewing preflight and obtaining GPU access

Install the previously used training stack (torch 2.11.0, transformers 5.18.0, TRL 1.15.0, PEFT 0.21.1,
datasets 4.8.5, bitsandbytes >=0.46.1) in the GPU runtime. Preserve the CPU-generated recipe files.
The separate directories below start new adapters from the base model; they do not resume the old adapter.

First perform the longest-example memory check, including two accumulated optimizer steps:

```bash
python -u -m scripts.train --config configs/docile-readable-4096-stress.yaml --max-steps 2
```

If it passes, the learning pilot can be run:

```bash
python -u -m scripts.train --config configs/docile-readable-4096-pilot.yaml --max-steps 32
python -u -m scripts.evaluate_docile --adapter checkpoints/docile-readable-4096-pilot --split train --limit 1 --max-new-tokens 3072 --sample --output outputs/docile-readable-training-probe
```

Review raw output, complete JSON/schema validity, field/text and grounding matches, and token-cap hits on
training pages before scaling. Training-page results are not evidence of generalization. Full training is
not started automatically. Teacher-forced validation is disabled in these configs to avoid encoding long
held-out targets during the T4 memory pilot. Generation-based validation must follow any candidate full run.
Keep the locked test set reserved until the recipe and selection decisions are settled.

The original full-page UI still uses a different schema; this recipe does not integrate the DocILE adapter
into that UI or establish vLLM serving latency.
