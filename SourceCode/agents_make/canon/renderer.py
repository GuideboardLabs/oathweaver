"""Scaffold renderer utilities for Canon v1 slot operations."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

_CANON_ROOT = Path(__file__).resolve().parent

_MARKER_TEMPLATES: dict[str, tuple[str, str]] = {
    ".py": ("# region: {name}", "# endregion: {name}"),
    ".js": ("// region: {name}", "// endregion: {name}"),
    ".html": ("<!-- region: {name} -->", "<!-- endregion: {name} -->"),
    ".css": ("/* region: {name} */", "/* endregion: {name} */"),
    ".sql": ("-- region: {name}", "-- endregion: {name}"),
    ".md": ("<!-- region: {name} -->", "<!-- endregion: {name} -->"),
}

_SLOT_NAME_RE = r"([a-z0-9-]+)"
_SLOT_DISCOVERY: dict[str, re.Pattern[str]] = {
    ".py": re.compile(rf"^[ \t]*# region: {_SLOT_NAME_RE}[ \t]*$", re.MULTILINE),
    ".js": re.compile(rf"^[ \t]*// region: {_SLOT_NAME_RE}[ \t]*$", re.MULTILINE),
    ".html": re.compile(rf"^[ \t]*<!-- region: {_SLOT_NAME_RE} -->[ \t]*$", re.MULTILINE),
    ".css": re.compile(rf"^[ \t]*/\* region: {_SLOT_NAME_RE} \*/[ \t]*$", re.MULTILINE),
    ".sql": re.compile(rf"^[ \t]*-- region: {_SLOT_NAME_RE}[ \t]*$", re.MULTILINE),
    ".md": re.compile(rf"^[ \t]*<!-- region: {_SLOT_NAME_RE} -->[ \t]*$", re.MULTILINE),
}

_REGION_NORMALIZERS: dict[str, re.Pattern[str]] = {
    ".py": re.compile(r"(?ms)(^[ \t]*# region: [^\n]+\n)(.*?)(^[ \t]*# endregion: [^\n]+[ \t]*\n?)"),
    ".js": re.compile(r"(?ms)(^[ \t]*// region: [^\n]+\n)(.*?)(^[ \t]*// endregion: [^\n]+[ \t]*\n?)"),
    ".html": re.compile(r"(?ms)(^[ \t]*<!-- region: [^\n]+ -->\n)(.*?)(^[ \t]*<!-- endregion: [^\n]+ -->[ \t]*\n?)"),
    ".css": re.compile(r"(?ms)(^[ \t]*/\* region: [^\n]+ \*/\n)(.*?)(^[ \t]*/\* endregion: [^\n]+ \*/[ \t]*\n?)"),
    ".sql": re.compile(r"(?ms)(^[ \t]*-- region: [^\n]+\n)(.*?)(^[ \t]*-- endregion: [^\n]+[ \t]*\n?)"),
    ".md": re.compile(r"(?ms)(^[ \t]*<!-- region: [^\n]+ -->\n)(.*?)(^[ \t]*<!-- endregion: [^\n]+ -->[ \t]*\n?)"),
}


def _template_for(file_path: Path) -> tuple[str, str]:
    suffix = file_path.suffix.lower()
    if suffix not in _MARKER_TEMPLATES:
        raise ValueError(f"Unsupported slot file extension: {suffix}")
    return _MARKER_TEMPLATES[suffix]


def _slot_pattern(file_path: Path, slot_name: str) -> re.Pattern[str]:
    open_tpl, close_tpl = _template_for(file_path)
    open_marker = re.escape(open_tpl.format(name=slot_name))
    close_marker = re.escape(close_tpl.format(name=slot_name))
    return re.compile(rf"(?ms)^(?P<open>[ \t]*{open_marker}[ \t]*\n)(?P<body>.*?)(?P<close>[ \t]*{close_marker}[ \t]*\n?)")


def _canon_path(canon_version: str) -> Path:
    path = _CANON_ROOT / canon_version
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Unknown canon scaffold: {canon_version}")
    return path


def _canon_relative(file_path: Path, canon_root: Path | None = None) -> str:
    """Return canon-style relative path for slot validator lookup."""
    path = Path(file_path)
    if canon_root is not None:
        try:
            return str(path.relative_to(Path(canon_root))).replace("\\", "/")
        except Exception:
            pass
    parts = path.parts
    if len(parts) >= 2 and parts[-2:] == ("templates", "index.html"):
        return "templates/index.html"
    if len(parts) >= 2 and parts[-2:] == ("static", "app.js"):
        return "static/app.js"
    if len(parts) >= 2 and parts[-2:] == ("static", "styles.css"):
        return "static/styles.css"
    return path.name


def copy_scaffold(canon_version: str, target_dir: Path) -> None:
    """Copy a scaffold directory into target_dir and pin canon version."""
    source = _canon_path(canon_version)
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        target_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    marker = str(canon_version).strip()
    marker_path = source / ".canon-version"
    if marker_path.exists():
        try:
            marker = marker_path.read_text(encoding="utf-8").strip() or marker
        except Exception:
            marker = marker
    (target_dir / ".canon-version").write_text(marker + "\n", encoding="utf-8")


def list_slots(target_dir: Path) -> dict[Path, list[str]]:
    """Return slot names discovered in files under target_dir."""
    found: dict[Path, list[str]] = {}
    for path in sorted(target_dir.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        suffix = path.suffix.lower()
        matcher = _SLOT_DISCOVERY.get(suffix)
        if matcher is None:
            continue
        text = path.read_text(encoding="utf-8")
        slots = [match.group(1) for match in matcher.finditer(text)]
        if slots:
            found[path] = slots
    return found


def read_slot(file_path: Path, slot_name: str) -> str:
    """Read content between region markers for one slot."""
    text = file_path.read_text(encoding="utf-8")
    pattern = _slot_pattern(file_path, slot_name)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Slot '{slot_name}' not found in {file_path}")
    return match.group("body").strip("\n")


def write_slot(
    file_path: Path,
    slot_name: str,
    content: str,
    *,
    validate: bool = True,
    canon_root: Path | None = None,
) -> None:
    """Write content between region markers for one slot."""
    if validate:
        from .slot_validators import SlotValidationError, validate_slot

        rel_path = _canon_relative(file_path, canon_root)
        violations = validate_slot(rel_path, slot_name, str(content or ""))
        if violations:
            raise SlotValidationError(violations)

    text = file_path.read_text(encoding="utf-8")
    pattern = _slot_pattern(file_path, slot_name)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Slot '{slot_name}' not found in {file_path}")

    new_body = str(content or "").rstrip() + "\n"
    replacement = f"{match.group('open')}{new_body}{match.group('close')}"
    updated = text[: match.start()] + replacement + text[match.end() :]
    file_path.write_text(updated, encoding="utf-8")


def fill_slot(file_path: Path, slot_name: str, content: str) -> None:
    """Alias for write_slot for clearer call sites."""
    write_slot(file_path, slot_name, content)


def _normalize_regions(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    pattern = _REGION_NORMALIZERS.get(suffix)
    if pattern is None:
        return text
    return pattern.sub(r"\g<1>__SLOT_CONTENT__\n\g<3>", text)


def verify_plumbing_intact(target_dir: Path, canon_version: str) -> list[str]:
    """Return relative file paths whose non-slot plumbing diverges from canon."""
    source = _canon_path(canon_version)
    divergences: list[str] = []

    allowed_text_suffixes = {".py", ".js", ".html", ".css", ".sql", ".md", ".txt", ".json"}
    for canon_file in sorted(source.rglob("*")):
        if not canon_file.is_file():
            continue
        if "__pycache__" in canon_file.parts or canon_file.suffix.lower() in {".pyc", ".pyo"}:
            continue
        rel = canon_file.relative_to(source)
        target_file = target_dir / rel
        if not target_file.exists() or not target_file.is_file():
            divergences.append(str(rel))
            continue
        if canon_file.suffix.lower() not in allowed_text_suffixes and canon_file.name != ".canon-version":
            continue

        canon_text = canon_file.read_text(encoding="utf-8")
        target_text = target_file.read_text(encoding="utf-8")
        if _normalize_regions(canon_file, canon_text) != _normalize_regions(target_file, target_text):
            divergences.append(str(rel))

    return divergences
