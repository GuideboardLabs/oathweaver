"""Structured spec model for Canon v1 web-app generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_KEBAB_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_ROUTE_RE = re.compile(r"^/api/[a-z][a-z0-9_]*(?:/<int:id>)?$")
_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


@dataclass
class FieldModel:
    """Describes one entity field."""

    name: str
    type: Literal["str", "int", "float", "bool", "date", "datetime", "json"]
    required: bool = True
    default: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FieldModel":
        name = str(payload.get("name", "")).strip()
        if not _SNAKE_RE.match(name):
            raise ValueError("field name must be snake_case")
        type_value = str(payload.get("type", "")).strip()
        if type_value not in {"str", "int", "float", "bool", "date", "datetime", "json"}:
            raise ValueError("field type is invalid")
        return cls(
            name=name,
            type=type_value,  # type: ignore[arg-type]
            required=bool(payload.get("required", True)),
            default=(str(payload.get("default")) if payload.get("default") is not None else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
        }


@dataclass
class Entity:
    """Describes one storage entity."""

    name: str
    fields: list[FieldModel]
    primary_key: str = "id"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Entity":
        name = str(payload.get("name", "")).strip()
        if not _SNAKE_RE.match(name):
            raise ValueError("entity name must be snake_case")
        primary_key = str(payload.get("primary_key", "id")).strip() or "id"
        if not _SNAKE_RE.match(primary_key):
            raise ValueError("primary_key must be snake_case")
        raw_fields = payload.get("fields") or []
        if not isinstance(raw_fields, list):
            raise ValueError("entity.fields must be an array")
        seen_field_names: set[str] = set()
        fields: list[FieldModel] = []
        for item in raw_fields:
            if not isinstance(item, dict):
                continue
            f = FieldModel.from_dict(dict(item))
            if f.name not in seen_field_names:
                fields.append(f)
                seen_field_names.add(f.name)
        return cls(name=name, fields=fields, primary_key=primary_key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "fields": [field.to_dict() for field in self.fields],
            "primary_key": self.primary_key,
        }


@dataclass
class Route:
    """Describes one API route."""

    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: str
    handler_name: str
    entity: str | None = None
    summary: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Route":
        method = str(payload.get("method", "")).strip().upper()
        if method not in {"GET", "POST", "PUT", "DELETE"}:
            raise ValueError("route method is invalid")
        path = str(payload.get("path", "")).strip()
        if not _ROUTE_RE.match(path):
            raise ValueError("route path must match /api/<plural> or /api/<plural>/<int:id>")
        handler_name = str(payload.get("handler_name", "")).strip()
        if not _SNAKE_RE.match(handler_name):
            raise ValueError("handler_name must be snake_case")
        raw_entity = payload.get("entity", "")
        entity = ("" if raw_entity is None else str(raw_entity)).strip() or None
        summary = str(payload.get("summary", "")).strip()
        if path.endswith("/<int:id>") and method not in {"GET", "PUT", "DELETE"}:
            raise ValueError("id routes must use GET, PUT, or DELETE")
        return cls(method=method, path=path, handler_name=handler_name, entity=entity, summary=summary)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "handler_name": self.handler_name,
            "entity": self.entity,
            "summary": self.summary,
        }


@dataclass
class View:
    """Describes one frontend view section."""

    name: str
    entity: str | None = None
    purpose: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "View":
        name = str(payload.get("name", "")).strip()
        if not _KEBAB_RE.match(name):
            raise ValueError("view name must be kebab-case")
        raw_entity = payload.get("entity", "")
        entity = ("" if raw_entity is None else str(raw_entity)).strip() or None
        purpose = str(payload.get("purpose", "")).strip()
        return cls(name=name, entity=entity, purpose=purpose)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entity": self.entity,
            "purpose": self.purpose,
        }


@dataclass
class AppSpec:
    """Root canon spec consumed by slot-fill pipeline."""

    app_name: str
    feature_summary: str
    entities: list[Entity] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)
    views: list[View] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "AppSpec":
        app_name = str(payload.get("app_name", "")).strip() or "Generated App"
        feature_summary = str(payload.get("feature_summary", "")).strip() or "Generated feature"

        raw_entities = payload.get("entities") or []
        raw_routes = payload.get("routes") or []
        raw_views = payload.get("views") or []
        if not isinstance(raw_entities, list) or not isinstance(raw_routes, list) or not isinstance(raw_views, list):
            raise ValueError("entities/routes/views must be arrays")

        entities = [Entity.from_dict(dict(item)) for item in raw_entities if isinstance(item, dict)]
        routes = [Route.from_dict(dict(item)) for item in raw_routes if isinstance(item, dict)]
        views = [View.from_dict(dict(item)) for item in raw_views if isinstance(item, dict)]

        if not entities:
            raise ValueError("entities must not be empty")
        if not routes:
            raise ValueError("routes must not be empty")
        if not views:
            raise ValueError("views must not be empty")

        entity_names = {entity.name for entity in entities}
        for route in routes:
            if route.entity and route.entity not in entity_names:
                raise ValueError(f"route entity '{route.entity}' not found in entities")

        handler_names = [route.handler_name for route in routes]
        if len(handler_names) != len(set(handler_names)):
            raise ValueError("route handler_name values must be unique")

        return cls(
            app_name=app_name,
            feature_summary=feature_summary,
            entities=entities,
            routes=routes,
            views=views,
            notes=str(payload.get("notes", "")).strip(),
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "feature_summary": self.feature_summary,
            "entities": [entity.to_dict() for entity in self.entities],
            "routes": [route.to_dict() for route in self.routes],
            "views": [view.to_dict() for view in self.views],
            "notes": self.notes,
        }


Field = FieldModel


def parse_spec_text(raw_text: str) -> AppSpec:
    """Parse model output text into an AppSpec object."""
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("empty spec text")
    block = _JSON_BLOCK_RE.search(text)
    candidate = block.group(0) if block else text
    payload = json.loads(candidate)
    if not isinstance(payload, dict):
        raise ValueError("spec payload must be a JSON object")
    return AppSpec.model_validate(payload)


def spec_to_json(spec: AppSpec) -> str:
    """Serialize AppSpec to stable pretty JSON."""
    return json.dumps(spec.model_dump(), indent=2, ensure_ascii=False, sort_keys=True)
