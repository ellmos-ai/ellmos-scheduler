# Third-Party Licenses & Dependency Transparency

Stand: 2026-10-02 (Audit-Historie: 2026-09-29, 2026-09-26, 2026-09-23, 2026-09-14, 2026-09-11)
Project: **ellmos-scheduler** (`ellmos-ai/ellmos-scheduler`)  
Maintainer: Lukas Geiger / ellmos-ai Core Team  
Ecosystem: [open-bricks](https://github.com/open-bricks)
Plain-Text Companion: [`THIRD_PARTY_LICENSES.txt`](THIRD_PARTY_LICENSES.txt)

---

## 1. Overview & Policy Statement

This is a selected declared-component license inventory with upstream references, not a
complete resolved/transitive SBOM or a current vulnerability clearance. The dated
inventory below remains historical; boundary review: 2026-10-16. TASK-SCHED-07
tracks dependency/advisory verification separately. Runtime declarations contain
the Python standard library and conditional Windows tzdata; executors can invoke
additional programs with their own dependencies and network behavior. RunAsInvoker
describes inherited caller permissions, not privilege reduction.

CI also installs `build` and `wheel`; their pinned workflow configuration is not
a complete license/advisory audit. Dependency audit work remains in TASK-SCHED-07.
See NOTICE for attribution and THIRD_PARTY_LICENSES.txt for the plain-text inventory.

---

## Level 1 SBOM Invariant Cross-Reference Matrix

| Invariant Code | Implemented mechanism | Evidence scope / remaining boundary |
|---|---|---|
| `INV-LOCAL-01` | SQLite scheduling state | No mandatory cloud scheduler; host policy controls executor/filesystem network use. |
| `INV-PRIV-02` | Caller permissions (RunAsInvoker) | No elevation request or automatic privilege drop. |
| `INV-CONC-03` | Transactional claims and deterministic run IDs | Valid leases serialize claims; expiry does not prove old processes stopped. |
| `INV-AUTH-04` | Two file reads and SHA-256 comparison | Configured sources must be trusted; file origins and IDs may be private. |
| `INV-STRM-05` | Strict configured output decoding | Captured output/error can still contain sensitive data. |
| `INV-EXEC-06` | Explicit argv and shell=False | Invoked programs retain their own behavior and caller permissions. |
| `INV-RES-07` | Direct-process timeout and abandoned claims | Descendant/resource and lease-limit validation remains open. |
| `INV-MOD-08` | Executor registry and consumer adapters | External programs/dependencies require their own controls. |
| `INV-PLAT-09` | Native CI test matrix | Python 3.10/3.13 on three OS families; platform skips and device acceptance remain separate. |
| `INV-SLA-10` | Local hash/readback records | No signatures or append-only storage; disclosure process is documented separately in SECURITY.md. |


---

## 2. Runtime Dependencies

| Package | Version Constraint | License | Component Purpose | Upstream Source |
|---|---|---|---|---|
| **`tzdata`** | `>=2024.1; platform_system == 'Windows'` | Apache-2.0 / Public Domain | IANA time zone database provider for Python `zoneinfo` on Windows environments | [PyPI](https://pypi.org/project/tzdata/) / [IANA](https://www.iana.org/time-zones) |
| **Python Standard Library** | `>=3.10` | PSFL (Python Software Foundation License 2.0) | Core runtime substrate (`sqlite3`, `datetime`, `zoneinfo`, `hashlib`, `json`, `subprocess`, `argparse`) | [Python Software Foundation](https://www.python.org/psf/license/) |

---

## 3. Development, Build & Testing Dependencies

| Package | Version Constraint | License | Purpose | Upstream Source |
|---|---|---|---|---|
| **`pytest`** | `>=8` | MIT | Unit and automated metadata contract test runner | [pytest.org](https://docs.pytest.org/) |
| **`tomli`** | `>=2; python_version < '3.11'` | MIT | PEP 517 / PEP 621 TOML parsing fallback for Python 3.10 | [PyPI](https://pypi.org/project/tomli/) |
| **`ruff`** | `>=0.6` | MIT / Apache-2.0 | High-performance static analysis, formatting and code hygiene | [astral.sh/ruff](https://astral.sh/ruff) |
| **`setuptools`** | `>=68` | MIT | PEP 517 compliant build backend and packaging metadata | [PyPI](https://pypi.org/project/setuptools/) |

---

## 4. Scope and verification limits

The mechanisms above are source-level descriptions, not blanket compliance PASS
certificates. Full payloads, truncated stored output/error and absolute file origins can
remain in the local state. Database writers can modify records. Deployment policy
must cover access control, backups, external programs and network restrictions.
Dependency resolution, transitive licenses and advisory status require a separate
reproducible audit; the inventory date alone proves none of these.

---

## 5. Dependency License Texts

### MIT License
*Applies to: `pytest`, `tomli`, `setuptools`, and parts of `ruff`.*

```text
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Apache License 2.0
*Applies to: `tzdata`, and parts of `ruff`.*

```text
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### Python Software Foundation License (PSFL 2.0)
*Applies to: Python Standard Library components.*

```text
1. This LICENSE AGREEMENT is between the Python Software Foundation ("PSF"), and
   the Individual or Organization ("Licensee") accessing and otherwise using this
   software ("Python") in source or binary form and its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
   grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
   analyze, test, perform and/or display publicly, prepare derivative works,
   distribute, and otherwise use Python alone or in any derivative version,
   provided, however, that PSF's License Agreement and PSF's notice of copyright,
   i.e., "Copyright (c) 2001-2026 Python Software Foundation; All Rights Reserved"
   are retained in Python alone or in any derivative version prepared by Licensee.
```
