# Slide Page Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge candidate screenshots into temporal PPT pages and send only representative images to the vision model, while retaining an OCR-only route.

**Architecture:** Python groups OCR frames using local text and image evidence after resampling, then analyzes representative images per group. Java persists the per-job visual mode and page result; Vue presents pages with original frame references. Existing frame evidence remains for compatibility.

**Tech Stack:** Python/OpenCV/FastAPI, Java 21/Spring Boot/MySQL, Vue 3/TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-27-slide-page-merge-design.md`

## Global Constraints

- Keep original frame timestamps and OCR blocks.
- `ocr_only` must never send images to the model; `both` uses group representatives.
- Preserve old stored results and retry the persisted job mode.
- Do not use live model calls for automated tests.

## Review Focus

- Gradually revealed text on one page groups together.
- A new problem on the same template stays separate.
- Blank transitions do not erase the adjacent page.
- Missing screenshots or malformed model replies preserve OCR evidence.
- Old JSON and frame authorization still work.

---

### Task 1: Page grouping in Python

**Files:** Create `agent-python/slide_grouping.py`, `agent-python/test_slide_grouping.py`.

**Interfaces:** `group_pages(visuals, keyframe_dir, segments, ask_json=None) -> (page_groups, transition_times)`.

- [ ] Write tests for progressive reveal, same-template new page, blank transition, representative selection, and sparse diagram.
- [ ] Run tests and confirm failure.
- [ ] Implement local OCR/image comparison, bounded ambiguous-boundary text review, page output.
- [ ] Run tests and confirm pass.

### Task 2: Analysis pipeline and mode

**Files:** Modify `agent-python/analysis.py`, `app.py`, `image_understanding.py` and their tests.

**Interfaces:** `analyze_file(file_id, visual_analysis_mode='both') -> dict`.

- [ ] Write tests showing OCR-only makes no image calls and both sends representatives only.
- [ ] Run tests and confirm failure.
- [ ] Wire grouping after review and image analysis onto groups, preserve raw evidence.
- [ ] Run tests and confirm pass.

### Task 3: Java result, mode persistence, and image access

**Files:** Modify Java controller/store/client, add Flyway migration, modify Java tests.

- [ ] Write tests for mode validation/persistence/retry, result compatibility and allowed group images.
- [ ] Run tests and confirm failure.
- [ ] Implement request propagation, JSON records and image authorization.
- [ ] Run Java tests and confirm pass.

### Task 4: Vue page presentation

**Files:** Modify `desktop/src/App.vue` and style as needed.

- [ ] Add page-based UI with mode selector and fallback for old frame results.
- [ ] Run TypeScript/build validation.

### Task 5: End-to-end verification

- [ ] Run Python tests, Java tests and frontend build.
- [ ] Inspect diff and record any unverified live-model behavior without triggering a costly full-video run.
