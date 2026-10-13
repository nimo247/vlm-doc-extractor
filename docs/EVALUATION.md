# Evaluation contract

All metrics are computed on selected manifest records. Ground-truth labels must be reviewed independently of the model under test. Generated samples only verify the implementation and data path.

## Quality metrics

| Metric | Definition | Limitation |
|---|---|---|
| Field accuracy | Correct predicted value or correct null / all gold fields | Includes easy absent fields; inspect emitted accuracy as well |
| Emitted field accuracy | Correct emitted values / all emitted values | Does not show extraction coverage; read with field accuracy |
| False extraction on absent fields | Non-null predictions for gold null fields / gold null fields | Requires intentionally absent/unreadable examples |
| Unsupported literal value rate | Emitted values not found anywhere in complete gold text / emitted values | Literal support, not field correctness or semantic hallucination; text labels must be complete |
| Table cell accuracy | Matching normalized cells at the same row/column / union-size cell grid | Sensitive to row alignment; no merged-cell support; not TEDS |
| Reading-order pair accuracy | Correct order of matched gold block pairs / matched pairs | Report block-match recall alongside it; unmatched blocks have no pairs |
| Block-match recall | One-to-one matched blocks / gold blocks | Greedy geometry/type/text matching, not optimal assignment |
| Character error rate | Levenshtein edits on normalized ordered document text / gold character count | Can exceed 1; structure changes also affect this measure |
| Schema-valid document rate | Successful parse and validation / attempted documents | Upstream failures also reduce it; inspect per-document errors |

Whitespace/case are normalized for text comparisons. Total fields additionally normalize decimal formatting and commas. Gold labels and predicted outputs remain verbatim; metric normalization does not rewrite exports.

Blocks are greedily matched by identical type, bounding-box IoU >=0.1, and text similarity >=0.35. Tables use that same matching. Unmatched gold and extra predicted table cells are penalized. If no prediction exists, gold fields/table cells are scored as incorrect and gold characters count as deletions. Reading-order metrics return null when no matched pairs exist.

## Honest comparison protocol

Keep model identifier, weights, prompt, image preprocessing, precision, generation budget, request concurrency, and hardware in run records. Compare zero-shot and fine-tuned versions of the same model before attributing a change to training. Use document-level bootstrap confidence intervals on a sufficiently large real test set. Do not tune on its outcomes.

The optional Docling export currently uses native Docling JSON. It is not fed into these metrics automatically. Write and verify a schema adapter before claiming a numerical comparison.

## Failure taxonomy

- Recognition: missing/incorrect characters or small text.
- Structure: omitted blocks, incorrect reading order, broken table rows.
- Extraction: text present but attached to the wrong field.
- Grounding: absent value invented; region does not cover actual image evidence.
- Abstention: unreadable field guessed, or readable field unnecessarily withheld.
- Runtime: timeout, truncated JSON, page omission, schema failure.

Label a reviewed sample of failures in each category and show representative images with predictions and gold labels. Quote-reference validation alone cannot detect model-generated false document text.
