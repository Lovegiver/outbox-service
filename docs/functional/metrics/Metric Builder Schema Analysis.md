# Metric Builder Schema Analysis

## BDD-016 lifecycle boundaries

BDD-016A is the read-only configuration analysis boundary. It enriches
`schema-fields` and hardens `preview`. BDD-016B adds the atomic `create`
boundary: it persists one `MetricDefinition`, its first immutable
`MetricDefinitionVersion`, and the compatibility with the exact selected
`SchemaDefinition` in one transaction. BDD-016C validates the complete public
lifecycle through explicit rebuild, explicit activation, real Events, workers,
MetricState and Prometheus.

The exact `SchemaDefinition.json_schema` is the only source of truth for a
field's type, required character and nullability. The Builder never asks the
user to redefine those properties.

## Conservative field analysis

Each field descriptor exposes `path`, `json_type`, `required`, `nullable`,
`analysis_status`, `analysis_reason`, `label_allowed`,
`label_rejection_reason`, `value_intents`, `cardinality_risk` and `warnings`.
The closed analysis statuses are:

- `SUPPORTED`: the schema construction and proposed Counter use are proven;
- `UNSAFE`: the construction is understood but cannot prove Counter or label
  safety;
- `UNSUPPORTED`: the construction is outside the bounded analyzer subset.

A nested path is required only when every property segment is listed in the
`required` array of its containing object. Nullability is separate and is
propagated through nullable ancestors.

The first subset supports objects, nested properties, arrays and their current
`[*]` paths, simple scalar types, one simple type unioned with `null`, scalar
enums, `minimum`, and numeric `exclusiveMinimum`. `$ref`, dynamic or external
references, `anyOf`, `oneOf`, `allOf`, recursive schemas and other complex
conditionals are returned as `UNSUPPORTED`, never guessed from branch order.

Analysis is bounded by `metrics.builder` configuration. Defaults are 20 enum
values, 5 labels, 512 path characters, 32 path segments, 32 schema levels,
1,000 fields and 128 characters per label name. Twenty enum values is a
deliberately conservative initial static cardinality ceiling, not a dynamic
budget.

## Counter intent contract

| Intent | Field contract | Transform | Counter proof |
| --- | --- | --- | --- |
| `count_event` | no value path, no label | `constant` | constant `1` |
| `count_by_label` | no value path, exactly one safe label | `constant` | constant `1` |
| `sum_value` | integer or number with proven lower bound >= 0 | `identity` | schema lower bound |
| `count_array_items` | array | `count` | length >= 0 |
| `measure_string_length` | string | `length` | length >= 0 |
| `count_boolean_true` | boolean | `to_number` | false=`0`, true=`1` |

`sum_value` is rejected when `minimum` is absent, negative or non-finite, or
when a supported numeric `exclusiveMinimum` still permits negative values.
Complex unions are `UNSUPPORTED`. BDD-015C remains the final defense and
rejects non-numeric, non-finite or negative runtime increments permanently.

An absent optional value or an explicitly allowed `null` produces no
observation and no artificial zero. A real `0`, empty string, empty array or
`false` produces the genuine zero contribution defined by its transform.
An absent or nullable label preserves a constant contribution with a
structural JSON `null` dimension. No business value is reserved;
`"__missing__"` remains ordinary data.

Compiler `1.1` persists `nullable` for value and label paths. Runtime accepts
historical compiler `1.0` plans with a conservative `nullable=false` default;
historical snapshots are not mutated or recompiled at runtime.
An internal contradiction is persisted with
`METRIC_VALUE_NULL_NOT_ALLOWED` or `METRIC_LABEL_NULL_NOT_ALLOWED`.

## Static label policy

Boolean fields and scalar enums at or below the configured limit are accepted.
Free strings and numbers, objects, arrays, oversized or non-scalar enums,
`id`/`*_id`, UUID, email, URL, phone, token, session, correlation, timestamp
and date/time fields are refused. Nullable labels use the same cardinality
decision; nullability affects extraction rather than widening allowed values.

This is a deterministic minimum safeguard. Per-metric, EventType or Project
budgets and observed runtime cardinality are future work.

## Input and name safety

Builder request models reject extra properties and unknown intents. Metric
codes use a positive bounded grammar, label names use Prometheus syntax and
the `ob1_` namespace is reserved. Paths must exactly match a canonical field
returned for the selected schema; filters, unions, scripts and arbitrary
expressions cannot be submitted. Schema depth, field count, path size, label
count and enum size are bounded.

The final Prometheus metric name is centrally calculated and returned as
read-only preview data. Existing codes are compared by their final normalized
name, so `sales-total` and `sales_total`, or `sales` and `ob1_sales`, cannot
silently converge. BDD-016B repeats that check under the stable EventType
scope lock. BDD-016C repeats it over the complete snapshot both during rebuild
and, under the exact schema lock, during activation. Historical or alternate
administration paths cannot bypass it. The renderer remains defensive.

SQLAlchemy repositories use bound parameters and no Builder input controls a
table, column or SQL clause. Free text such as apostrophes or markup is stored
as inert data. Output encoding belongs to the future frontend boundary. The
known frontend JWT and general YAML-import hardening are outside BDD-016A.

## Atomic Builder creation

`POST /api/admin/event-types/{event_type_id}/metric-builder/create` does not
trust a prior preview. In the transaction it locks the EventType, resolves and
locks the exact schema, reruns the bounded analysis and intent safeguards,
generates the YAML, and sends that exact text through `MetricYamlService` for
safe parsing, validation and compilation. Only then does it flush, in order:

1. the `MetricDefinition`;
2. its version number `1`;
3. the exact version/schema compatibility.

The orchestration service owns the single commit and every rollback. The
repositories only add, query, lock and flush, so identifiers are available
without an intermediate commit. Failure at any point leaves none of the three
rows behind and the session remains reusable.

The natural creation key is `EventType + metric code`. A functionally
identical replay returns the same three identifiers with HTTP `200` and
creates no version. Functional equality covers the definition name and
description, initial version label, exact schema compatibility, canonical
YAML content and deterministic compiled plan. The initial creation returns
HTTP `201`. Reusing the same key for different content returns
`BUILDER_METRIC_ALREADY_EXISTS` with HTTP `409`; it never creates an implicit
version 2.

Concurrent creation is serialized by locking the stable EventType row before
the exact SchemaDefinition row. This order is constant. It protects both the
natural key and Prometheus-name collision scan in the EventType scope without
a global lock. Identical requests converge on one triplet; incompatible
requests return a stable conflict after the winning transaction commits.
Existing PostgreSQL unique constraints remain the final protection for the
definition key, version number and exact compatibility.

Creation does not create a `ProcessingChain` or `ProcessingPlan`, does not
change an ACTIVE chain, and never invokes Event runtime processing. Rebuild
and activation remain explicit operations. A rebuild creates or reuses a
complete inactive DRAFT and preserves the current ACTIVE chain. Activation
revalidates the frozen snapshot before atomically retiring the previous ACTIVE
chain. Neither operation processes historical Events.

## End-to-end isolation and concurrency

Runtime selection uses persisted EventType and SchemaDefinition identities,
not structural JSON Schema equality. Two EventTypes with identical schema
documents therefore keep separate compatibilities, ProcessingChains,
executions, MetricState streams and platform-labelled Prometheus series.

Metric workers acquire both `MetricPlanExecution` and its
`MetricProcessingExecution` parent with PostgreSQL `FOR UPDATE SKIP LOCKED`.
This serializes plans of one Event snapshot while allowing two workers to drain
different Events concurrently. The demonstrated multi-worker guarantee applies
to metric-plan acquisition. Routing is materialized before it, and the BDD-016C
proof uses one aggregator; it does not claim concurrent aggregation workers.

## Initial performance baseline

`uv run python -m tests.performance.metric_pipeline_baseline` runs the representative
PostgreSQL profile: 100 Events of about 1 KiB, five Counter plans, four
concurrent HTTP producers, one metric worker and a metric batch of 100. It
reports ingress latency, queue wait, plan duration, observation and MetricState
availability, end-to-end latency, throughput and backlog drain as JSON and
Markdown under `/tmp` by default. A manual `workflow_dispatch` can publish the
same reports as CI artifacts.

Durable counts, exact MetricState deltas, duplicate detection and a bounded
completion timeout are blocking. Median, p95, p99, maximum and throughput are
observations only. Shared runners make this a comparative baseline, not an SLA
or an absolute capacity statement.
