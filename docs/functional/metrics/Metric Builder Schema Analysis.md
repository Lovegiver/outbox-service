# Metric Builder Schema Analysis

## BDD-016A boundary

BDD-016A is a read-only configuration analysis boundary. It enriches
`schema-fields` and hardens `preview`; it does not make Builder creation
atomic, create compatibilities, rebuild or activate ProcessingChains. Those
orchestration steps remain BDD-016B/C work.

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
silently converge. Transactional enforcement across concurrent creation is
part of the atomic BDD-016B create boundary; the renderer remains defensive.

SQLAlchemy repositories use bound parameters and no Builder input controls a
table, column or SQL clause. Free text such as apostrophes or markup is stored
as inert data. Output encoding belongs to the future frontend boundary. The
known frontend JWT and general YAML-import hardening are outside BDD-016A.

## Performance follow-up

BDD-016A adds no load harness or premature instrumentation. BDD-016C retains a
representative PostgreSQL baseline: 100 Events of about 1 KiB, five Counter
plans, four concurrent producers, one worker and a metric batch of 100. It
must separately report ingress latency, queue wait, plan duration,
observation/MetricState availability, end-to-end latency and backlog drain,
without an initial blocking threshold.
