"""Per-slot validators that reject data literals and malformed code."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SlotViolation:
    slot: str
    rule: str
    message: str


class SlotValidationError(ValueError):
    """Raised when one or more slot validators fail."""

    def __init__(self, violations: list[SlotViolation]) -> None:
        self.violations = list(violations)
        super().__init__(
            "; ".join(f"{v.slot}/{v.rule}: {v.message}" for v in self.violations)
            or "slot validation failed"
        )


def _is_data_literal_only(tree: ast.Module) -> bool:
    """Return True when a module contains only literal expressions."""
    if not tree.body:
        return False
    literal_nodes = (ast.Constant, ast.List, ast.Dict, ast.Tuple, ast.Set)
    for node in tree.body:
        if not isinstance(node, ast.Expr):
            return False
        if not isinstance(node.value, literal_nodes):
            return False
    return True


def validate_python_imports(content: str) -> list[SlotViolation]:
    if not content.strip():
        return []
    try:
        tree = ast.parse(content, mode="exec")
    except SyntaxError as exc:
        return [SlotViolation("imports-feature", "slot_syntax_error", str(exc))]
    if _is_data_literal_only(tree):
        return [SlotViolation("imports-feature", "slot_data_literal", "slot is bare data, not code")]
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            return [
                SlotViolation(
                    "imports-feature",
                    "non_import",
                    f"only Import/ImportFrom statements allowed; got {type(node).__name__}",
                )
            ]
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [str(alias.name or "").strip() for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [str(node.module or "").strip()]
        blocked = {"sqlalchemy", "flask_sqlalchemy"}
        for name in names:
            root = name.split(".", 1)[0].lower()
            if root in blocked:
                return [
                    SlotViolation(
                        "imports-feature",
                        "forbidden_dependency",
                        f"{root} is not allowed in canon app.py; use sqlite3 + get_db() helpers",
                    )
                ]
    return []


def validate_python_routes(content: str) -> list[SlotViolation]:
    if not content.strip():
        return []
    try:
        tree = ast.parse(content, mode="exec")
    except SyntaxError as exc:
        return [SlotViolation("routes-feature", "slot_syntax_error", str(exc))]
    if _is_data_literal_only(tree):
        return [SlotViolation("routes-feature", "slot_data_literal", "slot is bare data, not code")]

    has_route = False
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name):
                continue
            if decorator.func.value.id != "app":
                continue
            if decorator.func.attr not in {"get", "post", "put", "delete", "route", "patch"}:
                continue
            has_route = True
            break
        if has_route:
            break

    if not has_route:
        return [
            SlotViolation(
                "routes-feature",
                "no_route_decorator",
                "no @app.get/post/put/delete/route function found",
            )
        ]
    return []


def validate_sql_tables(content: str) -> list[SlotViolation]:
    if not content.strip():
        return [SlotViolation("tables", "empty", "tables slot must not be empty")]
    if not re.search(r"\bCREATE\s+TABLE\b", content, re.IGNORECASE):
        return [SlotViolation("tables", "no_create_table", "no CREATE TABLE statement")]
    if re.search(r"\bSERIAL\b", content, re.IGNORECASE):
        return [
            SlotViolation(
                "tables",
                "postgres_syntax",
                "SERIAL is PostgreSQL; SQLite uses INTEGER PRIMARY KEY AUTOINCREMENT",
            )
        ]
    if re.search(r"\bVARCHAR\s*\(\s*\d+\s*\)", content, re.IGNORECASE):
        return [SlotViolation("tables", "varchar_unnecessary", "SQLite TEXT is preferred over VARCHAR(N)")]
    creates = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?", content, re.IGNORECASE)
    if_not_exists = re.findall(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS", content, re.IGNORECASE)
    if len(creates) != len(if_not_exists):
        return [
            SlotViolation(
                "tables",
                "missing_if_not_exists",
                "every CREATE TABLE statement must use IF NOT EXISTS",
            )
        ]
    return []


def validate_sql_seeds(content: str) -> list[SlotViolation]:
    if not content.strip():
        return []
    allowed_prefixes = ("pbkdf2:", "scrypt:", "argon2:", "$2", "$argon2", "$pbkdf2")
    for line in content.splitlines():
        if "password_hash" not in line.lower():
            continue
        literals = [str(item or "").strip() for item in re.findall(r"['\"]([^'\"]+)['\"]", line)]
        has_hash_literal = any(lit.startswith(allowed_prefixes) for lit in literals if lit)
        if not has_hash_literal:
            return [
                SlotViolation(
                    "seeds",
                    "plaintext_password",
                    "password_hash seeds must use a real hash string",
                )
            ]
    return []


def validate_js_state(content: str) -> list[SlotViolation]:
    stripped = content.lstrip()
    if not stripped:
        return []
    if stripped.startswith("[") or stripped.startswith("{"):
        return [SlotViolation("state", "slot_data_literal", "slot starts with bare array/object")]
    if not re.search(r"\bref\s*\(|\breactive\s*\(", content):
        return [
            SlotViolation(
                "state",
                "no_reactive_binding",
                "state slot must declare ref() or reactive() bindings",
            )
        ]
    return []


def validate_js_methods(content: str) -> list[SlotViolation]:
    stripped = content.lstrip()
    if not stripped:
        return []
    if stripped.startswith("[") or stripped.startswith("{"):
        return [SlotViolation("methods", "slot_data_literal", "slot starts with bare array/object")]
    if not re.search(r"\b(async\s+)?function\s+\w+\s*\(|=\s*(async\s*)?\(", content):
        return [SlotViolation("methods", "no_function_def", "methods slot must define at least one function")]
    return []


def validate_js_computed(content: str) -> list[SlotViolation]:
    if not content.strip():
        return []
    if "computed(" not in content:
        return [SlotViolation("computed", "no_computed", "computed slot must call computed()")]
    return []


def validate_js_on_mounted(content: str) -> list[SlotViolation]:
    if not content.strip():
        return []
    if "onMounted(" not in content:
        return [SlotViolation("on-mounted", "no_on_mounted", "on-mounted slot must call onMounted()")]
    return []


def validate_html_view(content: str) -> list[SlotViolation]:
    if not content.strip():
        return []
    if not content.lstrip().startswith("<"):
        return [SlotViolation("view-feature", "not_html", "view-feature must start with an HTML tag")]
    return []


def validate_css_feature(content: str) -> list[SlotViolation]:
    if not content.strip():
        return []
    if "{" not in content or "}" not in content:
        return [
            SlotViolation(
                "feature-styles",
                "no_rules",
                "feature-styles must contain at least one CSS rule block",
            )
        ]
    if re.search(r"#[0-9a-fA-F]{3,8}\b", content):
        return [SlotViolation("feature-styles", "raw_hex_color", "raw hex colors forbidden; use var(--neu-*) tokens")]
    return []


VALIDATORS = {
    ("app.py", "imports-feature"): validate_python_imports,
    ("app.py", "routes-feature"): validate_python_routes,
    ("schema.sql", "tables"): validate_sql_tables,
    ("schema.sql", "seeds"): validate_sql_seeds,
    ("static/app.js", "state"): validate_js_state,
    ("static/app.js", "methods"): validate_js_methods,
    ("static/app.js", "computed"): validate_js_computed,
    ("static/app.js", "on-mounted"): validate_js_on_mounted,
    ("templates/index.html", "view-feature"): validate_html_view,
    ("static/styles.css", "feature-styles"): validate_css_feature,
}


def validate_slot(rel_path: str, slot_name: str, content: str) -> list[SlotViolation]:
    fn = VALIDATORS.get((str(rel_path), str(slot_name)))
    return fn(content) if fn else []
