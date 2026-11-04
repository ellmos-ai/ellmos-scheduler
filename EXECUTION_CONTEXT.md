# Scheduler execution context / Ausführungskontext

Stand: 04.11.2026. Source contract only; no agent dispatch or deployment.

## Target (SOLL)

A consumer executor can correlate a real native scheduler occurrence with its
own admitted worker generation, while retaining lease recovery, authority gates
and all existing two-argument executors.

## Implemented (IST)

`ExecutorRegistry.register_contextual(name, callback)` explicitly registers a
three-argument callback `(payload, timeout_seconds, context)`. The compatibility
`register` contract still invokes `(payload, timeout_seconds)` and never guesses
function signatures. Both registrations share the same namespace and require
`replace=True` to overwrite an existing name. `register_contextual_executor`
registers in the existing process-wide compatibility registry; no callback is
executed during registration. Raw `snapshot()` still maps names to callbacks;
register contextual mode explicitly when building another registry.

`SchedulerStore.start_run_context(run_id, worker_id=..., now=...)` uses the same
native admission transaction as `start_run`, additionally matching the persisted
claim worker. It returns frozen `ExecutionContext` metadata read from the admitted
run inside that transaction: `job_id`, `scheduled_for`, `run_id`, `attempt`,
`claimed_by`, `lease_expires_at`, `started_at`. Timestamps are canonical UTC strings.
The original `start_run` call retains its `None` return contract.

The service resolves and records required authorities before contextual admission.
User payload remains application data and is never read to construct or replace
context. Passing a payload dictionary as `context=` fails without invoking the
contextual executor. Context is host-side metadata, **not** an authority grant or
a sandbox against arbitrary Python plugins inside the host process.

`context.occurrence_id` is SHA-256 over the canonical `[job_id, scheduled_for]` pair.
It stays stable across abandoned-lease retry attempts, while `run_id`, `attempt`,
claim worker and lease may change. Distinct recurring due instants have distinct
occurrence IDs. It is an idempotency/correlation key, not proof of external effect,
execution success, task acceptance or a permission to start an agent.

## Deutsch: Grenzen der Lieferung

Der Kontext stammt ausschließlich aus dem nativen Run-Record. Rückgewinnung einer
abgelaufenen Lease erzeugt keinen neuen logischen Termin. Pause, Definitions- und
Autoritätsprüfungen bleiben wirksam; bestehende Zwei-Argument-Executoren bleiben
unverändert nutzbar. Kein Credential, Provider oder Worker wird dadurch aufgerufen.

Ein echter `bach-agent`-Executor mit Modell-/Konfigurations-CAS, korrelierter
Worker-Generation und unabhängigem Ergebnisnachweis ist ein nachfolgender Ausbau.
Die Kontextlieferung ist ausdrücklich kein abgeschlossener Agenten-Dispatch.
