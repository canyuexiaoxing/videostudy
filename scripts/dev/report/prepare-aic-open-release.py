"""Prepare first-party AGPL notices and source-only review scope."""
from pathlib import Path
from urllib.request import Request,urlopen
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
QA=ROOT/'.local/qa/aic-open-release-2026-10-25';QA.mkdir(parents=True,exist_ok=True)
URL='https://www.gnu.org/licenses/agpl-3.0.txt'
if not (ROOT/'LICENSE').exists():
    with urlopen(Request(URL,headers={'User-Agent':'Framewise-license-review'}),timeout=30) as r:text=r.read().decode('utf8')
    assert 'GNU AFFERO GENERAL PUBLIC LICENSE' in text and '19 November 2007' in text and len(text)>30000
    (ROOT/'LICENSE').write_text(text,encoding='utf8')
(ROOT/'NOTICE').write_text('''Framewise - course evidence-based learning workspace
Copyright (c) 2026 Framewise contributors.

First-party application code: GNU Affero General Public License version 3 only
(SPDX: AGPL-3.0-only), except files with a separate notice. See LICENSE.
This selection was confirmed by the project owner on 2026-10-25.

Third-party code, weights, runtimes, services and teaching materials retain their
own licenses and rights. See THIRD_PARTY_NOTICES.md. They are not relicensed by
this notice; NVIDIA software and remote services are not licensed under our AGPL.
Generative AI assisted implementation, debugging, tests and documentation.
The team reviews, modifies and validates adopted content and checks sources.
''',encoding='utf8')
(ROOT/'THIRD_PARTY_NOTICES.md').write_text('''# Third-party notices and submission scope

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
''',encoding='utf8')
p=ROOT/'README.md';s=p.read_text(encoding='utf8')
if '## 参赛核验入口（2026-10-25）' not in s:
    p.write_text('''## 参赛核验入口（2026-10-25）

当前自主代码采用 **AGPL-3.0-only**，全文见 [LICENSE](LICENSE)，权利边界见
[NOTICE](NOTICE) 和 [第三方资源与提交范围](THIRD_PARTY_NOTICES.md)。
当前原生桌面、SQLite与整课直生成流程请先看
[参赛运行与复核说明](docs/aic-review-2026-10-25/README.md)。
下方为早期开发记录，MySQL默认、固定端口和分块导图描述不代表当前原生入口。

---

'''+s,encoding='utf8')
p=ROOT/'scripts/dev/package/native-assemble.py';s=p.read_text(encoding='utf8')
start=s.find("    (licenses / 'THIRD-PARTY-NOTICES.txt').write_text(")
if start>=0:
    end=s.index("    critical_names =",start)
    s=s[:start]+"""    for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'):
        source = root / name
        plain(source)
        if not source.is_file():
            raise ValueError('license_notice_missing:' + name)
        shutil.copy2(source, licenses / name)
    (licenses / 'THIRD-PARTY-NOTICES.txt').write_text('Framewise first-party code: AGPL-3.0-only. See LICENSE, NOTICE and THIRD_PARTY_NOTICES.md. Components retain original licenses. Source-only review does not certify runtime redistribution.\\n', encoding='utf-8')
"""+s[end:]
    p.write_text(s,encoding='utf8')
state={'date':'2026-10-25','firstPartyLicense':'AGPL-3.0-only','licenseSource':URL,'licenseSha256':hashlib.sha256((ROOT/'LICENSE').read_bytes()).hexdigest(),'submissionScope':'source_only_no_dependencies_or_weights','binaryInstallerAudit':'separate_not_completed','paidRequests':0}
(QA/'license-decisions.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(state,ensure_ascii=False))
