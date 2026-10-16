# Sampled FFmpeg original frames and bounded cancellation I/O

> Execute inline with executing-plans; user explicitly approved implementation and comparison. Preserve current checkout and unrelated changes; no commit/push.

**Goal:** Remove per-decoded-frame filesystem polling overhead and feed Python only interval-selected full-resolution frames with real PTS, while retaining same-frame preview/save/OCR.

**Approved scope:** User conversation2026-10-16: first reduce disk cancellation polling, then implement FFmpeg interval output and compare on30MIN.mp4. Preserve region masks, YOLO, timestamps, rotation, cancellation/retry, bounded memory and existing mind-map behavior. No provider calls or historical course reanalysis.

**Architecture:** FrameRunGuard caches only disk polling up to200ms, with forced checks at save/publish boundaries and immediate in-memory stop checks. Keep PyAV sequential sampler as test/reference. Prototype FFmpeg select+lossless rawvideo NUT pipe; original media origin and raw PTS, no seeking/fps timestamp fabrication. FFmpeg child supervised for cancellation, errors and early close; output remains bounded by pipe/queues. Adopt it only after timestamp/pixel/resource tests and runtime comparison.

- [x] Tests first: disk poll bound and forced cancel, FFmpeg actual PTS/intervals/nonzero origin/VFR/rotation and subprocess cleanup.
- [x] Implement guard throttle and sample-only FFmpeg transport, preserve existing consumers and accurate supplementation.
- [x] Offline comparisons: same first60s, then whole30MIN coarse/save/OCR/local grouping, guard active and no paid calls. Preserve old baseline artifacts.
- [x] Full regression and independent review, handoff docs, deploy only with no in-flight jobs and offline deployed smoke.

Ruling: no new ML model, no asynchronous unbounded frame buffering, no automatic reruns. Existing saved images and history untouched. If FFmpeg is slower or incompatible, retain throttled PyAV and document evidence.

## Completion
452 tests passed (1 skipped); whole30MIN baseline69.108s, throttled PyAV80.376s, FFmpeg49.024s including GPU OCR/local grouping. Both new schemes75 identical timestamps/JPEG pixels. Real60s GPU-person check passed (31 samples/7 retained/19 detected-person frames). Review findings: label CPU main-process-only, add bounded classified decoder errors/exit code; fixed. Local service healthy and generated-media smoke confirms sampled-ffmpeg-pts-v2 and saved-before-callback. No paid calls, historical reanalysis, commit or push.
