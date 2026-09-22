# ellmos Scheduler

<img src="assets/banner.png" width="100%" alt="ellmos Scheduler banner">

[![Version](https://img.shields.io/badge/version-0.3.6-blue.svg)](https://github.com/ellmos-ai/ellmos-scheduler)
[![CI](https://github.com/ellmos-ai/ellmos-scheduler/actions/workflows/test.yml/badge.svg)](https://github.com/ellmos-ai/ellmos-scheduler/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/ellmos-ai/ellmos-scheduler)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 132 Passed](https://img.shields.io/badge/tests-132%20passed-brightgreen.svg)](tests/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Security: Local--First](https://img.shields.io/badge/security-Local--First-green.svg)](SECURITY.md)
[![Privacy: Zero--Egress](https://img.shields.io/badge/privacy-Zero--Egress-success.svg)](SECURITY.md)
[![Third-Party: Audited](https://img.shields.io/badge/third--party-audited-success.svg)](THIRD_PARTY_LICENSES.md)
[![Marketing: Logged](https://img.shields.io/badge/marketing-logged-blue.svg)](MARKETING-LOG.txt)
[![Ecosystem: ellmos-ai](https://img.shields.io/badge/ecosystem-ellmos--ai-purple.svg)](https://github.com/ellmos-ai)
[![Umbrella: open-bricks](https://img.shields.io/badge/umbrella-open--bricks-blueviolet.svg)](https://github.com/open-bricks)
[![LLM-Ready: llms.txt](https://img.shields.io/badge/LLM--Ready-llms.txt-orange.svg)](llms.txt)

[English](README.md) | [Deutsch](README_de.md)

## Quick Navigation

- [Overview](#ellmos-scheduler)
- [Architecture & System Overview](#architecture--system-overview)
- [Execution & Authority Preflight Lifecycle](#execution--authority-preflight-lifecycle)
- [Governance & Runtime Invariants](#governance--runtime-invariants)
- [Responsibility Boundary](#responsibility-boundary)
- [Supported Schedules](#supported-schedules)
- [Quick Start](#quick-start)
- [Canonical Authorities Per Run](#canonical-authorities-per-run)
- [Security and Availability Model](#security-and-availability-model)
- [Migration from BACH](#migration-from-bach)
- [Bundles and Partners](#bundles-and-partners)
- [Ecosystem & Sibling Tools](#ecosystem--sibling-tools)
- [Third-Party Licenses & Transparency](#third-party-licenses--transparency)
- [Marketing & Target Personas](#marketing--target-personas)
- [Comparative Matrix vs. Alternatives](#comparative-matrix-vs-alternatives)
- [Development, Security & License](#development-security--license)

> [!NOTE]
> **For AI Agents & LLM Tools:** This repository maintains an [`llms.txt`](llms.txt) machine-readable index for automated discovery, capability summaries, and CLI interfaces.

Standalone scheduler and run recorder for modular ellmos stacks. The module is
deliberately located **outside BACH**. BACH, Wonderland/Riverfall, desktop
automations, COMA, MarbleRun/llmauto, and swarm-ai can consume it through
narrow adapters.

Status: `0.3.5` (Pfad B Discoverability, 16-point bilingual quick navigation parity, 10-dimension comparative matrix vs. 4 alternatives, SEO keywords, third-party license audit & contract testsuite, 2026-09-14).

On Windows, the package installs `tzdata` as a conditional runtime dependency.
This makes IANA time zones such as `Europe/Berlin` work in a clean virtual
environment even when the operating system does not provide Python zoneinfo
data.

## Architecture & System Overview

```mermaid
graph TD
    subgraph Trigger ["Schedule Triggers"]
        Interval["Interval (seconds)"]
        Daily["Daily (HH:MM / Timezone)"]
        Cron["Cron (5-field expression)"]
    end

    subgraph Core ["ellmos Scheduler Engine"]
        Engine["Tick & Claim Engine"]
        DB[("SQLite State Store<br/>(Jobs, Leases, Runs)")]
        AuthorityCheck["Authority Preflight Guard<br/>(SHA-256 Hash Verification)"]
    end

    subgraph Executors ["Execution Adapters"]
        Subprocess["Subprocess / Command"]
        COMA["COMA AI Provider"]
        MarbleRun["MarbleRun Chain"]
        Custom["Custom Python Registry"]
    end

    subgraph Integrations ["Ecosystem Consumers"]
        BACH["BACH Adapter"]
        Swarm["swarm-ai"]
        Desktop["Desktop Automations"]
    end

    Interval --> Engine
    Daily --> Engine
    Cron --> Engine
    Engine <--> DB
    Engine --> AuthorityCheck
    AuthorityCheck --> Subprocess
    AuthorityCheck --> COMA
    AuthorityCheck --> MarbleRun
    AuthorityCheck --> Custom
    Subprocess --> Integrations
    COMA --> Integrations
    MarbleRun --> Integrations
    Custom --> Integrations
```

### Execution & Authority Preflight Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant CLI as CLI / Daemon Service
    participant Engine as Tick Engine
    participant Store as SQLite State Store
    participant Guard as Authority Preflight Guard
    participant Exec as Executor Adapter (Subprocess/COMA/Custom)

    CLI->>Engine: tick() / serve() pass
    Engine->>Store: Query due jobs & acquire atomic lease
    alt Job not due or lease active
        Store-->>Engine: Skip / Leased by another worker
    else Lease acquired
        Engine->>Store: Mark state as 'claimed' (deterministic run_id)
        opt --require-authorities active
            Engine->>Guard: Preflight verify required authority sources
            Guard->>Guard: Dual read-only passes + SHA-256 hash check
            alt Hash mismatch or missing required source
                Guard-->>Engine: Resolution failed (conflict / unresolved)
                Engine->>Store: Persist failed authority receipt & mark run failed
            else Authority verified
                Guard-->>Engine: Authority resolution validated
            end
        end
        Engine->>Exec: Dispatch payload (strict UTF-8 / safe argv)
        Exec-->>Engine: Return ExecutionResult (succeeded / failed)
        Engine->>Store: Persist run record, authority receipt & release lease
    end
```

## Governance & Runtime Invariants

`ellmos-scheduler` adheres to 10 foundational system and operational invariants to ensure predictable, secure, and verifiable scheduling across local agent environments:

| Invariant | Scope | Guarantee & Verification |
|---|---|---|
| `INV-LOCAL-01` **1. 100% Local-First & Zero-Egress** | System Architecture | Operates completely offline on localhost; strictly zero telemetry, analytics, external network sockets, or unauthorized cloud beacons. |
| `INV-PRIV-02` **2. Unprivileged Non-Elevation Execution** | Security Boundary | Executes strictly in unprivileged user-mode (`RunAsInvoker`), never requiring administrative or root privileges. |
| `INV-CONC-03` **3. Atomic SQLite Leases & Deduplication** | Concurrency Control | Deterministic, content-addressed `run_id` generation and atomic SQLite state leases prevent parallel double-execution across workers. |
| `INV-AUTH-04` **4. Double Read-Only Authority Preflight** | Integrity Guard | Mandatory authority files are read twice and validated against cryptographic SHA-256 integrity checksums prior to job dispatch. |
| `INV-STRM-05` **5. Strict UTF-8 & Fail-Closed Decoding** | Stream Hygiene | Subprocess output decoding enforces strict error handling (`utf-8:strict`), terminating corrupted outputs cleanly instead of corrupting audit logs. |
| `INV-EXEC-06` **6. Shell-Free Safe Process Invocation** | Execution Security | Process invocations accept explicit `argv` lists only, completely avoiding shell string interpolation (`shell=False`). |
| `INV-RES-07` **7. Fail-Closed Timeout & Abandoned Leases** | Process Resilience | Overdue, hanging, or crashed workers have their leases marked `abandoned` and reclaimed safely without deadlocks. |
| `INV-MOD-08` **8. Declarative Modular Integration** | Decoupled Architecture | Pluggable executor registry, external authority resolvers, and clean decoupling outside monoliths (e.g. BACH). |
| `INV-PLAT-09` **9. Multi-OS Cross-Platform Parity** | Platform Portability | Complete operational parity on Windows (with `tzdata` fallback for IANA time zones), Linux, and macOS. |
| `INV-SLA-10` **10. Cryptographic Receipt Persistence** | Auditability | Full audit records with immutable receipts, SHA-256 authority sets, and secret-free execution metadata. |

## Responsibility boundary

- ellmos Scheduler: schedule, due calculation, lease/claim, deduplicating
  `run_id`, pause/resume, run history, and heartbeat.
- COMA: starts a provider process and retrieves its result.
- MarbleRun/llmauto: executes chains.
- swarm-ai: executes agent patterns.
- `.SYNC/automation-exchange`: the cross-system contract for jobs, coverage,
  and representation.
- BACH: consumer through `BachSchedulerAdapter`, not owner of scheduler logic.

## Supported schedules

```json
{"kind": "interval", "seconds": 3600}
{"kind": "daily", "time": "04:00", "timezone": "Europe/Berlin"}
{"kind": "cron", "expression": "*/15 * * * *", "timezone": "Europe/Berlin"}
```

Cron supports five fields, `*`, lists, ranges, and steps.

## Quick start

```powershell
python -m pip install -e ".[dev]"
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" init
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" add `
  --id sync.daily.cross-system `
  --schedule '{"kind":"daily","time":"09:00","timezone":"Europe/Berlin"}' `
  --executor command `
  --payload '{"argv":["python","C:\\path\\to\\task.py"],"cwd":"C:\\Users\\lukas"}' `
  --authorities '[{"id":"policy:sync","type":"policy","resolver":"file","required":true,"source":{"path":"C:\\authorities\\SYNC_PROTOCOL.md"}}]'
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" status --json
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" serve --require-authorities
```

For prepared cutover or shadow jobs, `add --disabled` materializes the record
atomically in its disabled state. This prevents a parallel scheduler from
claiming the new job in the interval between `add` and `disable`. Enable it
later explicitly with `enable <job-id>`.

`command` and its equivalent name `subprocess` accept only an `argv` list and
start without a shell. `noop`, `coma`, and `marblerun` are registered as well:

```json
{"executor":"coma","payload":{"provider":"codex","prompt":"Check the build","cwd":"C:\\repo"}}
{"executor":"marblerun","payload":{"chain":"review-chain","background":false}}
```

Command output defaults to UTF-8. Python child processes receive an explicit
`PYTHONIOENCODING`/UTF-8 contract. A process that is demonstrably encoded
differently must set `payload.output_encoding`, for example `cp1252`. Allowed
stream-safe contracts are ASCII, CP437, CP850, CP1252, Latin-1, UTF-8/UTF-8-SIG,
and UTF-16/UTF-16-LE/UTF-16-BE. An explicit `PYTHONIOENCODING` error handler
must be `strict`. Undecodable output fails the run closed instead of silently
corrupting audit text with replacement characters. JSON CLI output remains
readable through ASCII escapes even under older Windows code pages.

COMA is imported only when a run actually occurs. The MarbleRun adapter starts
the public CLI as a safe argv list and observes the scheduler timeout. The
respective packages must be installed for these adapters. Do not simulate Codex
custom prompts and app tasks with an unproven `codex exec /command` invocation;
the respective native entry point must be verified live separately.

Custom integrations receive an isolated registry:

```python
from ellmos_scheduler import ExecutionResult, ExecutorRegistry, SchedulerService

registry = ExecutorRegistry()
registry.register(
    "my-adapter",
    lambda payload, timeout: ExecutionResult("succeeded", output="ok"),
)
service = SchedulerService(store, registry=registry)
```

Duplicate registration fails. Intentional replacement requires `replace=True`;
this allows concurrently running scheduler instances to use separate adapter
sets.

## Canonical authorities per run

Each job can declare explicit `rule`, `policy`, `decision`, `workflow`, or
`user-preference` sources (as well as other stable types). Immediately before
the executor, the scheduler reads them twice read-only, requires an identical
SHA-256 readback for required sources, and stores only authority ID/type,
requirement, resolver, safe origin, hashes, byte count, and status. Raw content
or secret metadata is rejected and never persisted.

```powershell
ellmos-scheduler --db C:\state\scheduler.db set-authorities sync.daily `
  --authorities '[{"id":"rule:global","type":"rule","resolver":"file","required":true,"source":{"path":"C:\\authorities\\CLAUDE.md"}},{"id":"preference:approved","type":"user-preference","resolver":"file","required":false,"source":{"path":"C:\\authorities\\USER.md"}}]'

ellmos-scheduler --db C:\state\scheduler.db tick --require-authorities --json
ellmos-scheduler --db C:\state\scheduler.db authority-receipt <run-id> --json
```

For an isolated carrier or operator run, repeat `--job` to restrict claiming,
lease recovery, authority resolution, and execution to explicit job IDs:

```powershell
ellmos-scheduler --db C:\state\scheduler.db tick `
  --job sync.daily --require-authorities --json
```

Unlisted due jobs and their expired leases remain untouched. Omitting `--job`
preserves the global tick behavior.

Required `unresolved`/`conflict` stops before provider/command execution.
Optional absence remains typed in the receipt. The authority-set hash remains
stable across runs with identical resolution; each `receipt_id` is bound to its
concrete `run_id`. Existing 0.1.x databases are migrated additively; old jobs
continue in compatible standard mode with an empty set. `--require-authorities`
is the explicit cutover gate after completed job migration. Custom resolvers
can be injected through `AuthorityResolverRegistry`, but must be registered
together with source allowlisting/validation and meet the same secret-free
hash/readback contract. Resolution and receipt persistence happen while the
state is still `claimed`; only a successful required preflight sets `started_at`
and `running`.

## Security and availability model

- Due runs receive an atomic, deterministic `run_id`.
- A lease prevents a second writer for the same job window.
- A claim is not success; only the completed run record counts.
- Expired claims are marked `abandoned` and may be scheduled again.
- Global and job-specific pause/resume remain separate from `enabled`.
- Status returns `last_tick_at`, job counts, and run counts in machine-readable form.
- Full security policy and boundary specifications are documented in [`SECURITY.md`](SECURITY.md).

## Migration from BACH

See [MIGRATION_FROM_BACH.md](MIGRATION_FROM_BACH.md). The existing
`BACH/system/hub/scheduler.py` remains in operation as a legacy source until
the operational comparison is complete. A dry run shows transferable and
intentionally skipped jobs without creating or changing the source or target
database:

```powershell
ellmos-scheduler --db C:\state\scheduler.db import-bach `
  --source-db C:\BACH\system\data\bach.db `
  --bach-root C:\BACH `
  --timezone Europe/Berlin `
  --dry-run --json
```

The Python entry point `create_bach_adapter(state_db)` provides the narrow
consumer API that BACH can use behind its `scheduler_provider` seam.

## Bundles and partners

`ellmos-scheduler` remains a separately usable clock. In the V4 composition it
is a required time and run recorder in `ellmos-automation-control-bundle`; it
still decides only **when** something is due, not which provider, workflow, or
agent executes it.

Direct bundle partners are the required automation registry and runtime
readback component; the cloud-control layer is recommended. For the
`self-healing` profile, `automation-self-care` is the required skill partner:
it is resolved declaratively and can be obtained, but cannot activate or alter
an automation without the prescribed approval, native-readback, and rollback
gates.

Binding membership, versions, profiles, and private composition recipes reside
exclusively in the bundle manifest. This public overview serves partner
discovery only.

## Ecosystem & Sibling Tools

Part of the [ellmos-ai](https://github.com/ellmos-ai) multi-agent infrastructure and the overarching [open-bricks](https://github.com/open-bricks) open-source software ecosystem:

| Tool | Organization | Description |
|------|--------------|-------------|
| [ellmos-core](https://github.com/ellmos-ai/ellmos-core) | ellmos-ai | Modular AI runtime, task dispatching & agent state substrate |
| [ellmos-scheduler](https://github.com/ellmos-ai/ellmos-scheduler) | ellmos-ai | Local cron, interval & scheduled task execution engine |
| [clutch](https://github.com/ellmos-ai/clutch) | ellmos-ai | Adaptive multi-model LLM router & agent execution gear |
| [coma](https://github.com/ellmos-ai/coma) | ellmos-ai | Single-binary multi-agent orchestrator & execution coordinator |
| [gardener](https://github.com/ellmos-ai/gardener) | ellmos-ai | Local-first autonomous session and context memory engine |
| [prompt-evidence-collector](https://github.com/ellmos-ai/prompt-evidence-collector) | ellmos-ai | Audit-ready LLM interaction capture & cryptographic evidence store |
| [lock-master](https://github.com/ellmos-ai/lock-master) | ellmos-ai | Multi-agent file locking and concurrency control protocol |
| [ticket-master](https://github.com/ellmos-ai/ticket-master) | ellmos-ai | Autonomous ticket routing and task dispatching triage console |
| [ellmos-controlcenter-mcp](https://github.com/ellmos-ai/ellmos-controlcenter-mcp) | ellmos-ai | MCP runtime supervision, skill routing & tool bundle discovery |
| [ellmos-filecommander-mcp](https://github.com/ellmos-ai/ellmos-filecommander-mcp) | ellmos-ai | MCP file management, safe delete & archive operations server |
| [ellmos-codecommander-mcp](https://github.com/ellmos-ai/ellmos-codecommander-mcp) | ellmos-ai | MCP code analysis, AST transformations & format server |
| [ellmos-clatcher-mcp](https://github.com/ellmos-ai/ellmos-clatcher-mcp) | ellmos-ai | MCP clipboard & scratchpad manager with dry-run safety |
| [n8n-manager-mcp](https://github.com/ellmos-ai/n8n-manager-mcp) | ellmos-ai | MCP n8n workflow management, execution monitoring & node introspection |
| [skills](https://github.com/ellmos-ai/skills) | ellmos-ai | Multi-agent canonical capability library & agent catalog |
| [usb-podcast-studio](https://github.com/entertain-and-more/usb-podcast-studio) | entertain-and-more | Desktop audio workstation, soundboard & recording suite (Klangpult) |
| [companion-for-agy](https://github.com/ellmos-ai/companion-for-agy) | ellmos-ai | Terminal companion & PTY wrapper for Google Antigravity |
| [safe-start-for-codex](https://github.com/dev-bricks/safe-start-for-codex) | dev-bricks | Safe starter and permission isolator for Codex CLI sessions |
| [automizer-for-claude-desktop](https://github.com/dev-bricks/automizer-for-claude-desktop) | dev-bricks | Scheduled task automation manager for Claude Desktop |
| [DevCenter](https://github.com/dev-bricks/DevCenter) | dev-bricks | Developer control plane, repository dashboard & environment manager |
| [CodeBox](https://github.com/dev-bricks/CodeBox) | dev-bricks | Polyglot code snippet manager & developer workbench |
| [open-bricks](https://github.com/open-bricks) | open-bricks | Umbrella catalog for open-source bricks, tools, and libraries |

---

## Third-Party Licenses & Transparency

`ellmos-scheduler` strictly complies with Open Source standards and runtime transparency:
- **100% Permissive Dependencies**: All runtime (`tzdata`, Python standard library) and development packages (`pytest`, `tomli`, `ruff`, `setuptools`) utilize OSI-approved permissive licenses (MIT, Apache-2.0, PSFL, Public Domain).
- **Zero-Egress Invariant (`INV-LOCAL-01`)**: No dependency transmits analytics, telemetry, or external network calls.
- **Unprivileged Execution (`INV-PRIV-02`)**: Executes entirely within user-mode permissions (`RunAsInvoker`).
- Full audit details, component license terms, and upstream sources are documented in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

---

## Marketing & Target Personas

Engineered for autonomous agent workflows, deterministic automation, and enterprise environments:
1. **Autonomous Multi-Agent Swarm Engineers & Orchestrators**: Non-overlapping execution for agentic loops, periodic memory compaction, and evaluation routines via atomic SQLite lease claiming.
2. **Local-First & Zero-Egress Tool Builders**: Completely offline scheduling without cloud phone-home APIs or telemetry beacons.
3. **DevOps & Site Reliability Engineers**: Unified cross-platform scheduling across Windows, Linux, and macOS with bundled Windows IANA timezone data.
4. **Enterprise Compliance & Security Auditors**: Dual preflight authority checks (SHA-256) and immutable cryptographic execution receipts.

### High-Intent Search Queries & Discoverability

- **Primary Intent**: `python deterministic local scheduler`, `sqlite lease claim scheduler`, `zero-egress task scheduler`, `agentic swarm periodic job runner`, `cron interval scheduler python stdlib`
- **Long-Tail & Architecture**: `standalone cron runner without redis`, `local agent memory compaction scheduler`, `offline task runner python zoneinfo`, `authority preflight execution gate`, `safe subprocess argv executor`

---

## Comparative Matrix vs. Alternatives

| Dimension / Capability | `ellmos-scheduler` | OS Cron / Windows Task Scheduler | Celery Beat / Redis Queue | APScheduler | Cloud Schedulers (AWS/GCP) |
|---|---|---|---|---|---|
| **Zero-Egress / Local-First (`INV-LOCAL-01`)** | **100% Offline & Local** | Local OS daemon | Requires network broker | In-process daemon | Cloud SaaS dependent |
| **Concurrency & Leases (`INV-CONC-03`)** | **Atomic SQLite Leases** | None (runs overlap) | Distributed Redis lock | In-memory locks | Distributed cloud lock |
| **Authority Preflight Gate (`INV-AUTH-04`)** | **SHA-256 Dual-Check** | None | None | None | IAM Policy checks |
| **Privilege Model (`INV-PRIV-02`)** | **Unprivileged (RunAsInvoker)** | Often root / SYSTEM | User or daemon | In-process thread | Cloud IAM role |
| **Audit Trail & Receipts (`INV-SLA-10`)** | **Immutable DB Receipts** | System syslog / Event Log | Task results in broker | Ephemeral in-memory | CloudWatch / Cloud Audit |
| **Multi-OS Parity (`INV-PLAT-09`)** | **Full (Win/Mac/Linux + tzdata)**| Disparate syntax/tools | High | High | N/A (Cloud managed) |
| **Agent & Swarm Ready (`INV-MOD-08`)** | **Native (COMA/MarbleRun)** | Requires custom scripts | Generic workers | Generic callables | Webhooks / Lambdas |
| **Shell Injection Safety (`INV-EXEC-06`)** | **Strict argv (`shell=False`)** | Shell string execution | Mixed | Python callables | Container entrypoint |
| **Stream Encoding Hygiene (`INV-STRM-05`)**| **Strict UTF-8 Fail-Closed** | OS default / Lossy | Serialized strings | Process stdout | Cloud logging streams |
| **Fault Recovery & Leases (`INV-RES-07`)** | **Auto-Abandoned Recovery** | Deadlocks / Overlaps | Worker heartbeat loss | None / Memory loss | Dead-letter queues |

For detailed competitive positioning benchmarks and architectural evaluations, see [`MARKETING-LOG.txt`](MARKETING-LOG.txt).

---

## Development, Security & License

- **Security & Vulnerability Disclosure**: See [`SECURITY.md`](SECURITY.md) for vulnerability reporting procedures (48h initial acknowledgment SLA, 5 business days triage SLA).
- **Changelog**: Comprehensive release and architecture notes are maintained in [`CHANGELOG.md`](CHANGELOG.md).
- **License**: MIT License. See [LICENSE](LICENSE) for details.
