# YOLO-only occlusion-aware page grouping

Approved scope: user requested modifying and testing only analyses with YOLO enabled (2026-10-18). This is a bounded fix to the existing pipeline, not the earlier pageCollections/forward-selection experiments.

- Keep explicit off path and its cache identity unchanged.
- Persist exact sampled person masks only for admitted frames, after original JPG save; bind mask to real PTS, image hash/dimensions, letterbox geometry, model and policy versions. Missing/invalid masks fall back to original grouping; never infer masks from nearby timestamps.
- Compare original 72%/65% retention under the common visible area only when masks explain missing OCR and sufficient independent body evidence remains. No broad fuzzy same-topic merge.
- Insufficient occluded evidence becomes a bounded pending tail until a later clear real frame resolves it. End-of-run or contradictory evidence conservatively splits. Incremental analysis must not publish pending groups prematurely.
- Preserve original imagery and OCR sources. Protect representative frames across newly merged occlusion boundaries so the direct map does not lose complementary content.
- No new inference/model calls, no automatic historical reanalysis, deployment, commit or push. Sidecar write errors log metadata-only diagnostics and fall back.
- Test persistence/invalidations, moving occlusion, tiny common area, different question, pending resolution/EOF, incremental publication, fallback, cancellation, disabled exact equivalence and all three pipeline wiring/cache paths. Evaluate existing real snapshots in isolated QA directories with the correctly configured local YOLO runtime if new masks are required.
