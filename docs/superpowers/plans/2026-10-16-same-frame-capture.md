# Same-frame sampled capture pipeline

> Implement inline using executing-plans. User approved the design and requested implementation; keep the current checkout and preserve unrelated uncommitted changes.

**Goal:** Select low-resolution previews and save the corresponding original decoded frames, with bounded queues feeding OCR before coarse sampling ends.

**Approved design:** Conversation 2026-10-16: sequential original-frame decode → resized preview selection → async atomic JPEG save → OCR → existing incremental grouping. At most a small fixed number of original frames may queue; rejected frames are released. Existing 2/3/4-second settings, regions and person selection policies remain. No paid model requests or historical course reanalysis.

**Architecture:** New frame_stream.py owns actual-PTS sequential sampling, bounded selection/save queues, run guards, and accurate supplementary capture. Reuse _candidate_times selection logic via injected decoded source and selected-frame callback; retain its legacy low-res-only path for baseline QA. analyze_visuals consumes saved same-frame records and publishes OCR events. Invalidate only visual/OCR cache stages through a pipeline version. Keep existing API records and group callbacks.

**Technology:** Existing PyAV dependency from faster-whisper, OpenCV, bounded Python queues/threads; no new model.

## Tasks
- [x] Add failing tests for actual PTS (including nonzero origin/VFR), same-frame bytes, bounded streaming and OCR-before-end, save/decoder errors, cancellation, original ROI/person selection compatibility and exact supplementary extraction from a long-GOP TS fixture.
- [x] Implement decoder and queues, integrate coarse decision callbacks while preserving previous/pending frames and original selection policy; atomic save and ordered OCR publication.
- [x] Correct supplementary timestamp extraction with verified backward preroll/fallback; version visual-only cache inputs and packaging, add bounded metadata diagnostics.
- [x] Run full Python regression in Linux container, adapt old batch-seek tests to the approved streaming contract. Run real-video offline accuracy/performance comparison including selection/save/OCR/grouping; forbid provider calls.
- [x] Independent review and repair, update handoff with measured resources/time and limitations. Deploy only with no in-flight jobs, verify offline in service. Do not commit/push without user request.

## Verification
Use generated long-GOP MPEG-TS and real power-series video. Compare requested 102/104/106 seconds to sequential decoded originals and verify images differ where source differs. Check single shared frame between preview and save, bounded queue backpressure, all producer/saver threads terminate, no callbacks after cancellation/failure, saved JPEG precedes OCR, generation of actual integer-ms time metadata, no reuse of old inaccurate-frame cache. Performance must include decode/coarse/save/OCR/local grouping; compare with legacy baseline and report cold/warm model behavior. Separate pipeline resources from ASR, which is not benchmarked unless explicitly included.

## Completion evidence
430 Python tests pass (1 skipped). Real 102/104/106-second captures match sequential decode; full visual-only comparison220.519s →212.969s. Short GPU-person integration passed. Reviewer findings repaired including deployment dependency. Local service updated, healthy; deployed generated-media smoke confirms same-frame-pts-v1/av18.1.0 and save-before-callback. No paid calls, history reanalysis, commits or pushes. See docs/same-frame-pipeline.md.
