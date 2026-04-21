# Output Spec

## Required artifacts

- Markdown output (`.md`)
- Raw OCR response (`.json`)
- Split markdown docs for each layout result (`<output-stem>_split/doc_{i}.md`)

## Markdown structure

- Starts with `# OCR Markdown Output`
- For layout parsing responses:
  - `## Document 0`, `## Document 1`, ...
  - Includes `markdown.text`
  - Includes downloaded/remote image references
- For generic OCR responses:
  - Splits by `## Page N`
  - Low-confidence lines are marked `[REVIEW score=0.xx]`

## Path conventions

- Intermediate OCR outputs can go to `tmp/ocr/`.
- Final handoff file should be under an explicit absolute path chosen by the caller.
- Downloaded image assets default to `<output-md-stem>_assets/`.
