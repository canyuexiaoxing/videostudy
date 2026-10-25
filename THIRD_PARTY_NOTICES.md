# Third-party notices and submission scope

Updated: 2026-10-25. First-party code: AGPL-3.0-only (LICENSE).

## Actual source archive scope

Includes first-party source, build/test scripts, configuration templates, authored
documentation and synthetic demonstration assets. Excludes installed dependencies,
model weights, runtime binaries, user courses, user data, credentials and Git history.
Installing dependencies separately does not waive their license obligations.
The old 0.3.1 online runtime payload on OBS is a separate binary distribution.

| Resource | License / terms | Decision for this source archive |
| --- | --- | --- |
| Ultralytics 8.4.4 / YOLO26n-seg | AGPL-3.0 / Enterprise alternative | AGPL route selected for first-party code. Provide source and build/test instructions to recipients. No Enterprise license claimed. No weights/wheels included. |
| faster-whisper / CTranslate2 / small weights | MIT declarations | ASR dependency; packages and weights obtained separately. Keep original notices on redistribution. |
| PaddleOCR / PaddlePaddle / PP-OCRv6 | Apache-2.0 declarations | OCR dependency; packages/weights excluded. Preserve license, NOTICE and modification notices where required. |
| PyTorch and Python dependencies | Individual package licenses | Requirements supplied; wheels and DLLs excluded. A runtime release must retain actual installed notices. |
| FFmpeg | Installed build declares LGPL v3 or later; no gpl/nonfree flags | No binary included. A binary release needs exact matching source/build information and applicable replacement/relinking rights. A generic website link alone is not asserted sufficient. |
| CUDA 12.6 / cuDNN 9.5 | NVIDIA EULAs, not AGPL | No DLLs, driver or toolkit included. Obtain separately under NVIDIA terms; root LICENSE grants no NVIDIA redistribution rights. |
| CPython / Temurin / Electron | PSF / GPLv2 with Classpath Exception / MIT plus component notices | Installed runtimes excluded. Obtain upstream; keep subcomponent notices in future binary bundles. |
| Vue / SimpleMindMap / KaTeX | MIT declarations; versions in desktop/package-lock.json | node_modules/dist excluded. Preserve upstream copyright and MIT text in bundled builds. |
| SQLite, JDBC, Spring, Flyway, optional MySQL connector | Each artifact's own license | JARs and database contents excluded. SQLite public-domain status is not its JDBC driver's license. Resolve dependencies from pom.xml. |
| DeepSeek-compatible API | Actual provider's service terms | Client code only, no remote weights or accounts. Each user supplies a key/endpoint and has rights to input data. Offline review requires no paid calls. |
| AI development tools | Applicable platform terms | Assistance disclosed. No credentials or private conversations included. Adopted content remains subject to source and rights review. |
| Interface demonstration | Authored synthetic lesson and preloaded demo data | Running source UI captured. Labeled interaction demonstration, not paid-model end-to-end performance. Existing third-party course frames excluded. |

## Primary sources

- https://www.gnu.org/licenses/agpl-3.0.html
- https://www.ultralytics.com/license
- https://github.com/ultralytics/ultralytics/blob/v8.4.4/LICENSE
- https://ffmpeg.org/legal.html
- https://docs.nvidia.com/cuda/archive/12.6.3/eula/index.html
- https://docs.nvidia.com/deeplearning/cudnn/backend/v9.5.1/reference/eula.html
- https://cdn.deepseek.com/policies/zh-CN/deepseek-open-platform-terms-of-service.html
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/PaddlePaddle/PaddleOCR

## Binary distribution boundary

This records what is redistributed in the source archive, not certification of
old installation packages. The existing OBS installer is not a newly audited
release. Exact FFmpeg source delivery, NVIDIA redistributables and all bundled
notices require a separate binary-release review. No installed user component is
deleted or disabled by this documentation work.

## Direct license texts and terms

See [LICENSE_LINKS.md](docs/aic-review-2026-10-25/LICENSE_LINKS.md) for 37 direct license/model-card/terms links, version scope and content checksums. The report embeds the same links as clickable L01-L37 references. OpenCV Python packaging is MIT; the underlying OpenCV 4.10 library is Apache-2.0. Torch, NumPy and PyAV main-project notices are BSD-3-Clause, with bundled libraries separately licensed. Exact installed notices retained under the review directory remain unchanged.
