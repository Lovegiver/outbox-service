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


class SchemaPathResolutionError(ValueError):
    pass


def resolve_path(schema_root: SchemaNode, path: str) -> ResolvedPath:
    tokens = parse_json_path(path)

    current_node = schema_root
    current_path = "$"
    iterator_path: str | None = None
    required = True

    for token in tokens[1:]:
        if token.token_type == "property":
            current_node, current_path, required = _resolve_property(
                current_node=current_node,
                property_name=_require_value(token),
                current_path=current_path,
                required=required,
            )
            continue

        if token.token_type == "array_each":
            current_node, current_path, iterator_path = _resolve_array_each(
                current_node=current_node,
                current_path=current_path,
            )
            continue

        raise SchemaPathResolutionError(f"Unsupported token: {token.token_type}")

    return ResolvedPath(
        path=path,
        json_type=current_node.json_type,
        iterator_path=iterator_path,
        required=required,
    )


def _resolve_property(
    current_node: SchemaNode,
    property_name: str,
    current_path: str,
    required: bool,
) -> tuple[SchemaNode, str, bool]:
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
    )


def _resolve_array_each(
    current_node: SchemaNode,
    current_path: str,
) -> tuple[SchemaNode, str, str]:
    if not isinstance(current_node, ArrayNode):
        raise SchemaPathResolutionError(
            f"Cannot iterate with '[*]' on non-array path '{current_path}'"
        )

    iterator_path = f"{current_path}[*]"

    return (
        current_node.items,
        iterator_path,
        iterator_path,
    )


def _require_value(token: JsonPathToken) -> str:
    if token.value is None:
        raise SchemaPathResolutionError("Token value is required")

    return token.value