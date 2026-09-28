# Page Evidence and Conditional Image Fallback Implementation Plan

**Goal:** Give both page routes time-aligned speech, give only the text route OCR, and send a second image only when the first image hides critical content that speech does not explicitly provide.

**Architecture:** A shared page-context builder assigns transcript segments to temporal page groups. A page-understanding service sends either ASR+OCR or ASR+one image to DeepSeek. The vision response has a structured occlusion decision; a local selector chooses one distinct image from the same group for a bounded second call. Raw OCR and frames remain available if model calls fail.

**Tech Stack:** Python 3.11, FastAPI, OpenCV, DeepSeek chat API, Java 21/Spring Boot, Vue 3.

**Spec:** `docs/superpowers/specs/2026-09-27-slide-page-merge-design.md`; refined by the 2026-09-28 user requirement: image route = speech text + image, text route = speech text + OCR text.

## Global Constraints

- Never include OCR text in an image-route model request; local OCR may still select candidates.
- Never include image bytes in an OCR-only model request.
- Keep page/frame timestamps and old stored-result compatibility.
- At most one extra image is sent per page; no full-video live model run for tests.

## Review Focus

- Page speech selection near sparse screenshot boundaries.
- A claimed occlusion that speech explicitly covers must not trigger another image.
- A duplicate candidate must not be resent.
- Malformed or failed model replies must preserve OCR and screenshot evidence.
- Java and Vue must read old and new result JSON.

---

### Task 1: Shared page context and route requests

**Files:** Create `agent-python/page_understanding.py` and `agent-python/test_page_understanding.py`.

- [x] Write tests for page ASR alignment and strict model payload separation.
- [x] Run tests to see failures, implement request builder and response validation, then rerun.

### Task 2: Conditional image fallback

**Files:** Extend `page_understanding.py` and its tests.

- [x] Test first-image-only success, speech-covered occlusion, missing critical content, duplicate alternatives and failed second call.
- [x] Run tests to see failures, implement one locally selected fallback, then rerun.

### Task 3: Pipeline and result display

**Files:** Modify `agent-python/analysis.py`, `test_analysis.py`, `test_analysis_integration.py`, `Dockerfile`, Java page result record, and Vue result presentation.

- [x] Test route-specific page requests, including transcript and evidence separation.
- [x] Implement page-level `textAnalysis` and updated image analysis; preserve legacy JSON.
- [x] Run Python, Java, and frontend tests/build; update the README and local deployment.
