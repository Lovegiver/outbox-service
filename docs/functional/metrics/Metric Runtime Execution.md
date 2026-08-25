# Metric Runtime Execution

## Runtime boundary

BDD-015C consumes configuration; it never creates or repairs it.

```text
Event.schema_definition_id
→ exact ACTIVE ProcessingChain
→ durable MetricProcessingExecution
→ one MetricPlanExecution per persisted ProcessingPlan
→ AnalyticalObservation
```

No active chain is a normal no-op. `DRAFT` and `INCOMPLETE` chains, a chain
for another schema and newer YAML versions are never fallbacks. The first
materialization freezes the chain and plan identifiers for the Event; later
technical retries keep that snapshot even if administration activates another
chain.

The runtime reads only `compiled_plan_json`. It does not parse YAML, validate
YAML, compile, invoke the Metric Builder, rebuild or activate configuration.

## Durable execution and isolation

`MetricProcessingExecution` records the Event/snapshot decision. Its targeted
child `MetricPlanExecution` records one technical execution per Event and
ProcessingPlan. PostgreSQL enforces both identities.

Plan states are:

- `PENDING`: materialized and ready;
- `RUNNING`: locked by the current transaction;
- `RETRYABLE`: technical failure eligible after `next_attempt_at`;
- `SUCCEEDED`: observations and success committed atomically;
- `FAILED_PERMANENT`: deterministic configuration/payload failure, or retry
  budget exhausted.

Parent snapshot states distinguish `MATERIALIZED`, transaction-local
`PROCESSING`, `SUCCEEDED`, `COMPLETED_WITH_ERRORS` and
`FAILED_CONFIGURATION`. No parent is created when no active chain exists.

The metric orders are materialized before the routing transaction may finish.
Execution then occurs independently from delivery. Each plan owns one
transaction/savepoint: a failure rolls back every observation of that plan but
does not undo successful plans, routing or deliveries. Metric retries never
replay a delivery.

Workers acquire eligible rows with `FOR UPDATE SKIP LOCKED`. The retry budget,
initial/capped exponential delay and batch size come from the `metrics.execution`
runtime configuration. Repositories never commit or roll back.

`RUNNING` is deliberately not leased or committed independently. Acquiring the
row, changing it to `RUNNING`, writing all observations and recording success
or failure remain in the same database transaction. If the worker dies before
commit, PostgreSQL rolls back the transient state and attempt increment, frees
the row lock and exposes the previous `PENDING` or `RETRYABLE` state to another
worker. A committed `RUNNING` state is therefore not part of this lifecycle.

## Observation identity and trace

Every runtime observation references:

- its Event;
- the frozen ProcessingChain;
- the ProcessingPlan and its execution;
- the MetricDefinition and MetricDefinitionVersion;
- a deterministic `observation_key`.

For compiler version `1.0`, the key is derived from the compiled observation
position and deterministic match occurrence. The database unique constraint on
`Event + ProcessingPlan + observation_key` prevents duplicate observations
after retry or replay. Historical observations remain readable with nullable
runtime references.

## Executable transform contract

Only operations with a defined and tested executor remain activable:

| YAML transform | Compiled operation | Runtime behavior |
| --- | --- | --- |
| `constant` | `constant` | emits `1` |
| `identity` | `identity` | emits the numeric value |
| `count` | `count` | emits the array length |
| `length` | `length` | emits the string length |
| `to_number` | `to_number` | emits `1` for true and `0` for false |

Previously declared transforms without a stable runtime meaning are rejected
during YAML validation and therefore cannot enter a newly activated snapshot.
They are `unique_count`, `occurrence_count`, `occurrence`, `timestamp`,
`hour_of_day`, `day_of_week`, `sum`, `avg`, `min` and `max`.
An unsupported operation found in an older/corrupt active plan is a durable
permanent failure; the runtime never recompiles it.

## Optional fields and labels

An absent optional `value_path` skips only that compiled observation. It emits
neither `0` nor `null` and does not fail the plan.

An absent optional label is stored structurally as JSON `null` in both
`AnalyticalObservation` and `MetricState`. A literal `"__missing__"`, an empty
string and `null` remain three distinct database values. Metrics Observatory
does not reserve any business label value.

At the Prometheus boundary, `null` and empty-string labels are omitted from the
canonical series identity. Internal Counter partitions that converge to the
same normalized metric name, platform labels and exposed business labels are
coalesced deterministically by addition. A literal `"__missing__"` remains
exposed normally and therefore stays distinct.

This coalescence relies on the additive semantics of the Counters currently
supported. It must not be generalized to future Gauges or Histograms without a
projection rule specific to those metric types. The renderer still rejects
non-numeric or negative values and conflicting metric names after
normalization, and verifies that no duplicate series remains after
coalescence.

## Incoherent active snapshots

An ACTIVE chain without plans produces a durable
`MetricProcessingExecution.FAILED_CONFIGURATION`. When a defective plan can be
identified, its `MetricPlanExecution` is persisted as `FAILED_PERMANENT` with
the explicit error. Missing compiled JSON, broken scope/compatibility and
unknown operations are never repaired by reading YAML or choosing another
snapshot. Routing and delivery remain independent.
