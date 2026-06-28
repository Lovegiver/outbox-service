# Test Infrastructure

## Philosophy

The test suite is treated as a client of the application.

Tests prepare an initial state, exercise the application through its public API, then observe the resulting state.

Tests must never depend on the application's internal implementation.

In particular:

* do not use SQLAlchemy models;
* do not use repositories to verify results;
* do not inspect service internals;
* verify observable behaviour only.

---

# Test Architecture

```
Record
    │
    ▼
ObjectFactory
    │
    ▼
Application
    │
    ▼
Probe
    │
    ▼
Assertions
```

## Record

A `Record` describes the data required to create a valid object.

Example:

```python
ProjectRecord(...)
```

A record represents an intention to create data.

It is **not** persisted.

---

## ObjectFactory

An `ObjectFactory` prepares the database before a test.

Factories use SQL directly.

Factories never use application repositories.

Factories return `PersistedObject` instances.

---

## PersistedObject

A `PersistedObject` represents an object that already exists in the database.

It contains only the information required by tests.

Example:

```python
PersistedProject
PersistedEventType
```

These objects are immutable.

---

## Probe

A `Probe` observes the database after the application has executed.

A probe never modifies the database.

A probe uses SQL directly.

Its purpose is to verify observable state.

---

# Design Rules

* Tests express business intent.
* SQLAlchemy models belong to the application, not to the tests.
* Repositories belong to the application, not to the tests.
* Factories prepare data.
* Probes observe data.
* Assertions remain simple and expressive.
* Keep the infrastructure small and easy to extend.

Whenever possible, prefer expressive business objects over primitive identifiers.
