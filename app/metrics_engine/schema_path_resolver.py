from __future__ import annotations

from dataclasses import dataclass

from app.metrics_engine.json_path import JsonPathToken, parse_json_path
from app.metrics_engine.schema_graph import ArrayNode, ObjectNode, SchemaNode


@dataclass(frozen=True)
class ResolvedPath:
    path: str
    json_type: str
    iterator_path: str | None
    required: bool
    nullable: bool


class SchemaPathResolutionError(ValueError):
    pass


def resolve_path(schema_root: SchemaNode, path: str) -> ResolvedPath:
    tokens = parse_json_path(path)

    current_node = schema_root
    current_path = "$"
    iterator_path: str | None = None
    required = True
    nullable = current_node.nullable

    for token in tokens[1:]:
        if token.token_type == "property":
            current_node, current_path, required, nullable = _resolve_property(
                current_node=current_node,
                property_name=_require_value(token),
                current_path=current_path,
                required=required,
                nullable=nullable,
            )
            continue

        if token.token_type == "array_each":
            current_node, current_path, iterator_path, nullable = _resolve_array_each(
                current_node=current_node,
                current_path=current_path,
                nullable=nullable,
            )
            continue

        raise SchemaPathResolutionError(f"Unsupported token: {token.token_type}")

    return ResolvedPath(
        path=path,
        json_type=current_node.json_type,
        iterator_path=iterator_path,
        required=required,
        nullable=nullable,
    )


def _resolve_property(
    current_node: SchemaNode,
    property_name: str,
    current_path: str,
    required: bool,
    nullable: bool,
) -> tuple[SchemaNode, str, bool, bool]:
    if not isinstance(current_node, ObjectNode):
        raise SchemaPathResolutionError(
            f"Cannot access property '{property_name}' on non-object path '{current_path}'"
        )

    if property_name not in current_node.properties:
        raise SchemaPathResolutionError(
            f"Property '{property_name}' does not exist at path '{current_path}'"
        )

    child_required = property_name in current_node.required

    return (
        current_node.properties[property_name],
        f"{current_path}.{property_name}",
        required and child_required,
        nullable or current_node.properties[property_name].nullable,
    )


def _resolve_array_each(
    current_node: SchemaNode,
    current_path: str,
    nullable: bool,
) -> tuple[SchemaNode, str, str, bool]:
    if not isinstance(current_node, ArrayNode):
        raise SchemaPathResolutionError(
            f"Cannot iterate with '[*]' on non-array path '{current_path}'"
        )

    iterator_path = f"{current_path}[*]"

    return (
        current_node.items,
        iterator_path,
        iterator_path,
        nullable or current_node.items.nullable,
    )


def _require_value(token: JsonPathToken) -> str:
    if token.value is None:
        raise SchemaPathResolutionError("Token value is required")

    return token.value
