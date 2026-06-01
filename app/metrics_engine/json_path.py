from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


JsonPathTokenType = Literal["root", "property", "array_each"]


@dataclass(frozen=True)
class JsonPathToken:
    token_type: JsonPathTokenType
    value: str | None = None


class JsonPathError(ValueError):
    pass


def parse_json_path(path: str) -> list[JsonPathToken]:
    if not path.startswith("$."):
        raise JsonPathError(f"Path must start with '$.': {path}")

    raw_parts = path[2:].split(".")

    if not raw_parts or any(part == "" for part in raw_parts):
        raise JsonPathError(f"Invalid JSON path: {path}")

    tokens: list[JsonPathToken] = [JsonPathToken("root")]

    for part in raw_parts:
        if part.endswith("[*]"):
            property_name = part[:-3]

            if not property_name:
                raise JsonPathError(f"Invalid array wildcard segment: {path}")

            tokens.append(JsonPathToken("property", property_name))
            tokens.append(JsonPathToken("array_each"))
            continue

        if "[" in part or "]" in part:
            raise JsonPathError(
                f"Only '[*]' array wildcard is supported in v1: {path}"
            )

        tokens.append(JsonPathToken("property", part))

    return tokens