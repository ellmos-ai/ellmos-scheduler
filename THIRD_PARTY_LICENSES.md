# Third-Party Licenses & Dependency Transparency

Stand: 2026-09-23
Project: **ellmos-scheduler** (`ellmos-ai/ellmos-scheduler`)  
Maintainer: Lukas Geiger / ellmos-ai Core Team  
Ecosystem: [open-bricks](https://github.com/open-bricks)

---

## 1. Overview & Policy Statement

`ellmos-scheduler` is dedicated to strict **Local-First & Zero-Egress** principles (`INV-LOCAL-01`) and executes exclusively in unprivileged user space (`INV-PRIV-02`, RunAsInvoker). To guarantee deterministic operation, auditability, and zero supply-chain lock-in, all runtime, testing, and build dependencies are rigorously vetted against the following criteria (with canonical attribution defined in [`NOTICE`](NOTICE)):

- **100% Permissive Open-Source & Level 1 SBOM**: Only OSI-approved permissive licenses (MIT, Apache-2.0, BSD-3-Clause, PSFL, Public Domain) are permitted. Strict copyleft (GPL, AGPL) is forbidden.
- **Zero-Egress & Offline Determinism**: No third-party dependency is allowed to establish unsolicited outbound telemetry, cloud beacons, or network phone-home sockets.
- **Minimal Surface**: Runtime dependencies are intentionally minimized. The core scheduling engine relies exclusively on Python standard library modules (`sqlite3`, `zoneinfo`, `subprocess`, `hashlib`, `json`), with a single platform-conditional runtime package on Windows (`tzdata`).

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

## 4. Invariant Compliance Assurances

All declared dependencies and runtime behaviors strictly comply with the 10 Governance & Runtime Invariants:
- **INV-LOCAL-01 (100% Local-First & Zero-Egress)**: None of the declared runtime or dev dependencies transmit network payloads, metrics, or telemetry across localhost boundaries.
- **INV-PRIV-02 (Unprivileged Non-Elevation Execution)**: Neither runtime nor build components require elevated administrator, root, or kernel permissions (`RunAsInvoker`).
- **INV-CONC-03 (Atomic SQLite Leases & Deduplication)**: Standard library `sqlite3` manages atomic concurrency without external network brokers.
- **INV-AUTH-04 (Double Read-Only Authority Preflight)**: Authority files verified via standard library `hashlib` SHA-256 before any job execution.
- **INV-STRM-05 (Strict UTF-8 & Fail-Closed Decoding)**: All textual IO, process stream decoding, and receipt handling rely on strict encoding standards without silent data loss.
- **INV-EXEC-06 (Shell-Free Safe Process Invocation)**: Execution uses `subprocess` with explicit argv lists and `shell=False`.
- **INV-RES-07 (Fail-Closed Timeout & Abandoned Leases)**: Expired or hanging executions are reclaimed safely without deadlock.
- **INV-MOD-08 (Declarative Modular Integration)**: Completely decoupled outside monoliths with narrow adapters for BACH and COMA.
- **INV-PLAT-09 (Multi-OS Cross-Platform Parity)**: Uniform cross-platform execution on Windows, Linux, and macOS (with `tzdata` fallback).
- **INV-SLA-10 (Cryptographic Receipt Persistence & Security SLAs)**: Cryptographic execution receipts persisted locally in SQLite; 48h initial response SLA for vulnerabilities.

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
