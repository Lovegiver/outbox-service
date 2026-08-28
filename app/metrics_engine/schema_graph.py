from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

JsonType: TypeAlias = Literal[
    "object",
    "array",
    "string",
    "number",
    "integer",
    "boolean",
    "null",
    "unknown",
]


@dataclass(frozen=True)
class SchemaNode:
    json_type: JsonType
    nullable: bool


@dataclass(frozen=True)
class ObjectNode(SchemaNode):
    properties: dict[str, SchemaNode] = field(default_factory=dict)
    required: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ArrayNode(SchemaNode):
    items: SchemaNode


@dataclass(frozen=True)
class ScalarNode(SchemaNode):
    pass


class SchemaGraphError(ValueError):
    pass


def build_schema_graph(schema: dict) -> SchemaNode:
    json_type = schema.get("type")
    nullable = False

    if isinstance(json_type, list):
        json_type, nullable = _simple_nullable_type(json_type)

    if json_type == "object":
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        return ObjectNode(
            json_type="object",
            nullable=nullable,
            properties={
                name: build_schema_graph(child_schema)
                for name, child_schema in properties.items()
            },
            required=required,
        )

    if json_type == "array":
        items_schema = schema.get("items")

        if not isinstance(items_schema, dict):
            raise SchemaGraphError("Array schema must define an object 'items' schema")

        return ArrayNode(
            json_type="array",
            nullable=nullable,
            items=build_schema_graph(items_schema),
        )

    if json_type in {"string", "number", "integer", "boolean", "null"}:
        return ScalarNode(json_type=json_type, nullable=nullable)

    return ScalarNode(json_type="unknown", nullable=False)


def _simple_nullable_type(types: list[str]) -> tuple[JsonType, bool]:
    """Resolve exactly one supported type plus null without order bias."""
    supported = {"object", "array", "string", "number", "integer", "boolean"}
    if any(not isinstance(item, str) for item in types):
        return "unknown", False
    members = set(types)
    non_null = members - {"null"}
    if len(non_null) == 1 and len(members) == 2:
        effective = next(iter(non_null))
        if effective in supported:
            return effective, True  # type: ignore[return-value]
    return "unknown", False
