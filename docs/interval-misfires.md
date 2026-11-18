# Interval misfires and opt-in coalescing

Version 0.3.7 exports MISFIRE_POLICY_SCHEMA = "ellmos.scheduler.misfire-policy.v1".
Consumers check this capability before constructing a state-writing adapter.
The package version alone is not a capability or build provenance receipt.

## Policy contract

| Policy | Missed occurrence handling | Allowed schedules |
| --- | --- | --- |
| replay (default) | Admit the earliest due occurrence and advance one occurrence. Every missed occurrence remains eligible. | All supported schedules |
| coalesce_latest | Admit the latest due point on the original interval grid, then advance one interval. | Positive interval schedules only |

Opt in only when the consumer declares that one current check replaces missed
checks, such as an idempotent repository delta scan. Financial postings,
delivery obligations and periodic tasks requiring individual occurrences must
retain replay. The scheduler cannot infer whether an executor is idempotent.

The original due timestamp anchors the interval grid. Coalescing never resets
that grid to the wall-clock tick. Integer timedelta division preserves
microsecond precision. Calculation is constant time even after weeks of
inactivity; the next due point remains strictly later than the observed tick.

claim_due keeps the native writer transaction, job filtering, enabled/exhausted
controls and existing authority/admission checks. It does not overlap an active
coalesced claim. The active-claim filter precedes the SQL limit, so an occupied
delta does not consume another job's slot.

## Honest execution history

A coalesced run is one execution, not many synthetic successes. The run row and
returned claim contain:

- scheduled_for: latest due point selected for this execution.
- misfire_policy: policy of this specific attempt.
- coalesced_from: first omitted due point, or null when none was omitted.
- coalesced_count: earlier occurrences omitted, excluding the selected occurrence.

These fields describe scheduling, not successful execution. Normal claimed,
running, succeeded, failed, timed_out and abandoned receipts retain their
meaning. No omitted occurrence is inserted as a run or reported as successful.
Latest-success projection continues to require an actual successful run.

An expired claimed/running attempt is abandoned through normal native recovery.
Its retry keeps its original scheduled_for, attempt lineage and coalescing
receipt, even when policy changed after expiry. Once that occurrence completes,
subsequent unclaimed intervals can coalesce. Failures and timeouts retain the
existing next-occurrence behavior; no unbounded retries are introduced.

For coalescing jobs, pending retries are selected independently of next_due_at.
That cursor records the admission high-water and never moves backwards for a
retry. Every occurrence whose latest attempt is abandoned remains eligible,
including when successful occurrences separate two abandoned ones. A completed
retry resolves only its own occurrence.

On the first native claim after migrating a legacy replay cursor that had
already been rewound, claim_due restores the cursor from recorded admissions.
The policy CAS still does not change a date. For example: admitted 00:00 and
00:02 expire, while 00:01 has succeeded. At 00:05:01 the new policy retries
00:00 and 00:02 with their original receipts, then coalesces only the unadmitted
00:03/00:04 points into a fresh 00:05 occurrence. The completed 00:01 run is
neither repeated nor counted as omitted.

## Creation and native CAS migration

New jobs pass misfire_policy="coalesce_latest" to SchedulerStore.add_job.
For an existing job, read a current store.list_jobs snapshot, then call:

    updated = store.set_misfire_policy(
        job["id"], "coalesce_latest",
        expected_generation=job["generation"],
        expected_policy=job["misfire_policy"],
    )

The method reads and updates within BEGIN IMMEDIATE. Production time is sampled
after acquiring the writer transaction. It rejects stale snapshots with
JobPolicyConflict("stale_job_policy") and unexpired claimed/running attempts
with JobPolicyConflict("active_claim"), including exact lease expiry.
After a conflict re-observe; do not bypass the check or edit the database.
Explicit now values are for controlled clocks/tests; production normally lets
the store obtain the current time.

A change increments the job generation. It does not change next_due_at,
schedule, payload, enabled state, authority configuration or run history.
Switching to replay uses the same CAS from the current due point; it does not
invent runs for earlier coalesced intervals.

## Migration and rollout

SchedulerStore.init adds policy/receipt columns to old state, defaulting
existing jobs and attempts to replay with no omitted occurrences. Historical
receipts are not reinterpreted. Read-only inspection never migrates a database.
The historical f2740ba7 schema is retained as a data-free test fixture.

1. Record actual installed source/build and take a read-only SQLite backup.
2. Test on an isolated copy using an executor registry unable to dispatch
   production commands or tasks.
3. Install the reviewed module before its capability-requiring consumer.
   Coordinate the single owner and ensure no active claim at policy migration.
4. Let the consumer validate the definition and call the native CAS.
5. Verify one coalesced execution, then other due work, and actual terminal
   receipts before declaring runtime success.

Old binaries do not understand the policy and continue replay. Rollback requires
a stopped/coordinated owner and an explicit policy/build decision. Do not run
old and new writers concurrently.

## BACH boundary

Only bach.docs.delta opts in. Four documentation routines retain replay and
their 14/14/60/30-day definitions. The canonical create_documentation_scheduler
facade checks the capability before adapter construction. BACH validates
existing definitions and migrates via this module; it has no separate due
arithmetic or direct SQL migration.

Tests cover weeks of backlog with limit one, exact time boundaries, parallel
claims, policy-update races, active/expired claims, default replay, failed and
timed-out outcomes, and migration from the historical schema.
