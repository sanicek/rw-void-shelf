# Artwork Provenance And Approval

## Current Asset

`About/Preview.png` is the tracked preview recovered with Steam Workshop item
`3008773339`. No editable source, generation receipt, or deterministic processing
recipe is currently tracked. Preserve the image as a recovered publication
artifact rather than implying that its provenance can be reconstructed.

The image is package content but not maintained code: do not add explanatory
metadata to the binary or rewrite it merely to normalize encoding. Repository
documentation owns its provenance and replacement policy.

## Replacement Workflow

The repository currently has no artwork manifest or automation wrapper. Until a
reproducible pipeline is deliberately adopted, replacement is an explicit,
human-reviewed process:

1. Keep credentials, raw generations, provider receipts, working files,
   candidates, and comparison sheets outside version control.
2. Present the final-size candidates and record their source, license, and any
   processing performed.
3. Obtain explicit user selection and approval before replacing the tracked
   preview. A general request for new artwork is not approval of a candidate or
   a paid generation charge.
4. Validate the approved PNG and the resulting mod package before committing.
5. Record durable attribution or licensing requirements in repository
   documentation when the approved source requires them.

Only the approved game-ready output belongs in `About/`. Do not claim ad hoc
resizing, generation, or conversion is reproducible; adopting automation later
requires documenting its inputs, outputs, external state, and approval gates.
