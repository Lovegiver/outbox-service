# Outbox AGENT

## Project purpose

Outbox is a standalone service responsible for:

- receiving events
- validating payloads
- routing events
- exposing metrics

Outbox produces and exposes data.

Outbox does NOT become:

- a BI platform
- a dashboard builder
- a Grafana replacement
- a time-series database
- a workflow engine

Specialized tools remain specialized:

- Prometheus → collection
- Grafana → visualization
- External systems → consumption

---

## Technical stack

- FastAPI
- Uvicorn
- PostgreSQL
- SQLAlchemy 2
- Alembic

---

## Source of truth

Always fix problems at the source.

Order of implementation:

```text
Models
→ Alembic migration
→ Database
→ Repository
→ Service
→ API
```

Never:

- modify DB manually to compensate
- patch generated artifacts
- fix runtime issues directly in SQL

---

## SQLAlchemy conventions

Always use SQLAlchemy 2 style.

Use:

```python
statement = (
    select(UserAccount)
    .where(UserAccount.email == email)
)

result = db.execute(statement)

return result.scalar_one_or_none()
```

Do not use:

```python
db.query(...)
```

Preferred patterns:

- `Mapped`
- `mapped_column`
- `select()`
- `execute()`
- `scalar_one_or_none()`
- `TYPE_CHECKING` where appropriate

---

## Imports

Respect the real project structure.

Never invent packages or paths.

Examples:

```text
Enums        → app/core
Models       → app/models
Repositories → app/repositories
Services     → app/services
```

Use `TYPE_CHECKING` for relationship imports when appropriate.

---

## Development workflow

Do not silently remove code.

Do not simplify code only to suppress IDE warnings.

If implementation details are uncertain, ask for:

- current file content
- project tree
- database schema
- migration content

Do not assume.

---

## Architectural philosophy

Extension: yes  
Modification: no

New functionality should integrate into the architecture instead of bypassing it.

Before adding a feature ask:

> Does Outbox produce this data,
> or is Outbox trying to exploit this data?

If Outbox produces it:

```text
→ implement in Outbox
```

If Outbox exploits it:

```text
→ prefer specialized tools
```