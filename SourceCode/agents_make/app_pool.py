"""App generation pool — Canon v1 scaffold + slot-fill for Flask/Vue/SQLite.

Pipeline (sequential):
    1. spec_generator       — emits structured AppSpec JSON
    2. scaffold_copy        — copies canon/web_app_v1 baseline
    3. db_architect         — fills schema slots (tables/seeds)
    4. api_implementer      — fills app.py feature slots + compile/smoke checks
    5. vue_architect        — plans frontend from spec/routes
    6. vue_implementer      — fills app.js/index.html feature slots
    7. integration_check    — detects route/fetch/schema mismatches
    8. integration_fixer    — re-fills impacted slots only
    9. css_writer           — fills feature-styles slot (token-safe)
   10. readme_writer        — fills README feature slots

Output: canon-structured app artifacts written to:
    Projects/{slug}/implementation/{ts}_app/
"""

from __future__ import annotations

import json
import importlib.util
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from shared_tools.feedback_learning import FeedbackLearningEngine
from shared_tools.model_routing import lane_model_config
from shared_tools.ollama_client import OllamaClient
from agents_make.canon import copy_scaffold, read_slot, verify_plumbing_intact, write_slot
from agents_make.canon.app_spec import AppSpec, parse_spec_text, spec_to_json
from agents_make.canon.lints import run_policy_lints


# ---------------------------------------------------------------------------
# SQLite canonical patterns — injected into every Python-generating agent
# ---------------------------------------------------------------------------

_SQLITE_PATTERNS = """\
# Validated against: sqlite3 stdlib on Python 3.12+

SQLite canonical patterns — follow these exactly:

1. Connection lifecycle using flask.g:
   import sqlite3
   from flask import g

   DATABASE = 'app.db'

   def get_db():
       if 'db' not in g:
           g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
           g.db.row_factory = sqlite3.Row   # dict-like row access
           g.db.execute("PRAGMA foreign_keys = ON")
           g.db.execute("PRAGMA journal_mode = WAL")
           g.db.execute("PRAGMA synchronous = NORMAL")
       return g.db

   @app.teardown_appcontext
   def close_db(e=None):
       db = g.pop('db', None)
       if db is not None:
           db.close()

2. Schema initialization:
   def init_db():
       with app.app_context():
           db = get_db()
           with open('schema.sql', 'r') as f:
               db.executescript(f.read())
           db.commit()

3. Always use parameterized queries — never f-strings or % in SQL:
   db.execute("INSERT INTO items (name, value) VALUES (?, ?)", (name, value))
   db.execute("SELECT * FROM items WHERE id = ?", (item_id,))

4. Schema conventions:
   - Every table gets: id INTEGER PRIMARY KEY AUTOINCREMENT
   - Timestamps: created_at TEXT DEFAULT (datetime('now', 'utc'))
   - Booleans: INTEGER (0/1)
   - Foreign keys: REFERENCES parent(id) ON DELETE CASCADE
   - Always add indexes on foreign key columns

5. Row to dict:
   row = db.execute("SELECT * FROM items WHERE id = ?", (id,)).fetchone()
   if row is None:
       return jsonify({"error": "not found"}), 404
   return jsonify(dict(row))

6. Batch fetch:
   rows = db.execute("SELECT * FROM items ORDER BY created_at DESC").fetchall()
   return jsonify([dict(r) for r in rows])
"""

_SQLITE_GOTCHAS = """\
SQLite gotchas:
- `PRAGMA foreign_keys = ON` must be set per connection.
- `executescript()` is for trusted schema files only (no user data).
- Use one connection per request via flask.g (connections are not thread-safe).
- Do not mix positional `?` placeholders with named placeholders accidentally.
- Convert `sqlite3.Row` to `dict(row)` before jsonify.
- Python 3.12 deprecated implicit datetime adapter behavior; prefer ISO strings or explicit conversion.
- Pair DML with explicit commit()/rollback().
- Never accept `ATTACH DATABASE` paths from request input.
"""

# ---------------------------------------------------------------------------
# Vue 3 CDN canonical patterns — injected into frontend-generating agents
# ---------------------------------------------------------------------------

_VUE3_PATTERNS = """\
# Validated against: Vue 3.5, served from unpkg CDN (prod build)

Vue 3 CDN pattern — no build step, loaded via unpkg CDN:

1. HTML entry point structure:
   <!DOCTYPE html>
   <html lang="en">
   <head>
     <meta charset="UTF-8">
     <meta name="viewport" content="width=device-width, initial-scale=1.0">
     <title>App Title</title>
     <link rel="stylesheet" href="/static/styles.css">
   </head>
   <body>
     <div id="app"><!-- Vue mounts here --></div>
     <script src="https://unpkg.com/vue@3.5/dist/vue.global.prod.js"></script>
     <script src="/static/app.js"></script>
   </body>
   </html>

2. app.js structure using Vue 3 global build:
   const { createApp, ref, reactive, computed, onMounted, watch } = Vue;

   const app = createApp({
     setup() {
       // state
       const items = ref([]);
       const loading = ref(false);
       const error = ref('');

       // API client — use fetch(), no axios
       async function fetchItems() {
         loading.value = true;
         try {
           const res = await fetch('/api/items');
           if (!res.ok) throw new Error(await res.text());
           items.value = await res.json();
         } catch(e) {
           error.value = e.message;
         } finally {
           loading.value = false;
         }
       }

       async function createItem(data) {
         const res = await fetch('/api/items', {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify(data),
         });
         if (!res.ok) throw new Error(await res.text());
         return res.json();
       }

       onMounted(fetchItems);
       return { items, loading, error, fetchItems, createItem };
     },

     // Template: use inline template or <template> in HTML
   });

   app.mount('#app');

3. Always use v-bind, v-on, v-for with :key, v-if/v-else.
4. Prefer ref() for primitives/single values and reactive() for nested state not destructured.
5. For forms: use v-model on ref() values.
6. No build step means no SFC (.vue files) — all in one app.js.
"""

_VUE3_GOTCHAS = """\
Vue 3 gotchas:
- ref() values require `.value` in script; templates auto-unwrap.
- Destructuring a reactive() object loses reactivity unless using toRefs.
- v-for without :key causes subtle rendering bugs.
- Every template reference must exist in setup() return.
- Do not define both inline HTML template and app.js template: at once.
- Avoid eager invocation in handlers; prefer function references in @click.
- Avoid async setup() unless using Suspense.
- Do not use `this` inside setup().
- watch(..., { immediate: true }) runs before onMounted.
"""

# ---------------------------------------------------------------------------
# Flask API canonical patterns
# ---------------------------------------------------------------------------

_FLASK_PATTERNS = """\
# Validated against: Flask 3.0+, Python 3.12+

Flask API canonical patterns:

1. Module-global app shape:
   from flask import Flask, jsonify, request
   from flask_cors import CORS
   app = Flask(__name__)
   CORS(app)
   app.config['JSON_SORT_KEYS'] = False

2. Standard CRUD route shapes:
   GET    /api/items          → list all
   POST   /api/items          → create (body: JSON)
   GET    /api/items/<int:id> → get one
   PUT    /api/items/<int:id> → update (body: JSON)
   DELETE /api/items/<int:id> → delete

3. Schema initialization without before_first_request:
   def init_db():
       with app.app_context():
           db = get_db()
           with open('schema.sql', 'r') as f:
               db.executescript(f.read())
           db.commit()

   with app.app_context():
       init_db()

4. Error handling:
   @app.errorhandler(404)
   def not_found(e):
       return jsonify({"error": "not found"}), 404

   @app.errorhandler(400)
   def bad_request(e):
       return jsonify({"error": str(e)}), 400

5. Input validation — always validate before writing:
   data = request.get_json(silent=True)
   if not data or 'name' not in data:
       return jsonify({"error": "name required"}), 400

6. Always return JSON. Never return HTML from API routes.
"""

_FLASK_GOTCHAS = """\
Flask gotchas:
- `@app.before_first_request` is removed in Flask 2.3+; do not emit it.
- Ensure `from flask_cors import CORS` exists before calling CORS(app).
- Convert datetime/Decimal before jsonify.
- Choose request.get_json(silent=True) + manual validation for bad payload handling.
- Remember methods=... on non-GET routes.
- Do not mutate flask.g outside request/app context.
- debug=True is dev-only; never claim it is production-ready.
- Convert sqlite rows with dict(row) before jsonify.
"""


# ---------------------------------------------------------------------------
# Zero-model-call quality checkers
# ---------------------------------------------------------------------------

# Known stdlib top-level package names for Python < 3.10 (no sys.stdlib_module_names)
_STDLIB_EXTRAS: frozenset[str] = frozenset({
    "abc", "argparse", "ast", "asyncio", "base64", "builtins", "cgi",
    "collections", "contextlib", "copy", "csv", "dataclasses", "datetime",
    "decimal", "email", "enum", "functools", "glob", "gzip", "hashlib",
    "hmac", "html", "http", "importlib", "inspect", "io", "itertools",
    "json", "logging", "math", "mimetypes", "multiprocessing", "operator",
    "os", "pathlib", "pickle", "platform", "pprint", "queue", "random",
    "re", "secrets", "shutil", "signal", "socket", "sqlite3", "ssl",
    "stat", "string", "struct", "subprocess", "sys", "tempfile", "textwrap",
    "threading", "time", "traceback", "typing", "unicodedata", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "xmlrpc", "zipfile",
    "zlib", "__future__",
})

_IMPORT_RE = re.compile(r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE)


def _check_dependencies(flask_code: str) -> tuple[list[str], list[str]]:
    """Parse imports in flask_code, return (present_third_party, missing_third_party)."""
    raw_packages = set(_IMPORT_RE.findall(flask_code))
    try:
        stdlib_names: frozenset[str] = sys.stdlib_module_names  # type: ignore[attr-defined]
    except AttributeError:
        stdlib_names = _STDLIB_EXTRAS
    third_party = [p for p in sorted(raw_packages) if p not in stdlib_names]
    present: list[str] = []
    missing: list[str] = []
    for pkg in third_party:
        try:
            if importlib.util.find_spec(pkg) is not None:
                present.append(pkg)
            else:
                missing.append(pkg)
        except (ModuleNotFoundError, ValueError):
            missing.append(pkg)
    return present, missing


class _HTMLChecker(HTMLParser):
    """Tracks structural invariants that would break Vue template compilation."""

    _BLOCK_TAGS: frozenset[str] = frozenset({
        "div", "section", "article", "main", "header", "footer", "nav",
        "form", "table", "thead", "tbody", "tr", "ul", "ol",
    })

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self.issues: list[str] = []
        self.has_app_div = False
        self.has_vue_cdn = False
        self.has_app_js = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if tag == "div" and attr_dict.get("id") == "app":
            self.has_app_div = True
        if tag == "script":
            src = attr_dict.get("src") or ""
            if "vue" in src.lower():
                self.has_vue_cdn = True
            if "app.js" in src:
                self.has_app_js = True
        if tag in self._BLOCK_TAGS:
            self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self._BLOCK_TAGS:
            return
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        elif tag in self._stack:
            # Drain stack to find matching open tag
            while self._stack and self._stack[-1] != tag:
                self.issues.append(f"Unclosed <{self._stack.pop()}> before </{tag}>")
            if self._stack:
                self._stack.pop()


def _check_html_structure(index_html: str) -> list[str]:
    """Check index.html for structural issues that would break Vue. Zero model calls."""
    issues: list[str] = []
    checker = _HTMLChecker()
    try:
        checker.feed(index_html)
    except Exception as exc:
        return [f"HTML parse error: {exc}"]

    if not checker.has_app_div:
        issues.append('Missing <div id="app"> — Vue has no mount target.')
    if not checker.has_vue_cdn:
        issues.append("Missing Vue 3 CDN <script> tag.")
    if not checker.has_app_js:
        issues.append("Missing /static/app.js <script> tag.")
    for unclosed in checker._stack:
        issues.append(f"Unclosed block tag: <{unclosed}>")
    issues.extend(checker.issues)
    # v-for without :key causes Vue warnings and potential rendering bugs
    vfor_lines = [
        l.strip() for l in index_html.splitlines()
        if "v-for" in l and ":key" not in l and "key" not in l
    ]
    for line in vfor_lines[:5]:
        issues.append(f"v-for without :key: {line[:120]}")
    return issues


_JS_KEYWORDS: frozenset[str] = frozenset({
    "true", "false", "null", "undefined", "this", "new", "return",
    "if", "else", "for", "while", "switch", "case", "break", "continue",
    "function", "const", "let", "var", "await", "async", "typeof", "in", "of",
})
_JS_GLOBALS: frozenset[str] = frozenset({
    "Math", "Date", "JSON", "Number", "String", "Boolean", "Array", "Object",
    "console", "window", "document", "fetch", "parseInt", "parseFloat", "isNaN",
    "isFinite", "Intl", "URL", "URLSearchParams", "setTimeout", "clearTimeout",
    "setInterval", "clearInterval", "Promise", "Error", "RegExp", "encodeURIComponent",
    "decodeURIComponent", "event",
})
_VUE_GLOBALS: frozenset[str] = frozenset({
    "Vue", "createApp", "ref", "reactive", "computed", "watch", "onMounted",
    "onUnmounted", "nextTick",
})


def _balanced_block(text: str, open_idx: int, open_ch: str = "{", close_ch: str = "}") -> tuple[str, int] | None:
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != open_ch:
        return None
    depth = 0
    quote: str | None = None
    escape = False
    for i in range(open_idx, len(text)):
        ch = text[i]
        if quote:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == quote:
                quote = None
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            continue
        if ch == open_ch:
            depth += 1
            continue
        if ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i], i
    return None


def _split_top_level_csv(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth_round = 0
    depth_square = 0
    depth_curly = 0
    quote: str | None = None
    escape = False
    for ch in text:
        if quote:
            buf.append(ch)
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == quote:
                quote = None
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            buf.append(ch)
            continue
        if ch == "(":
            depth_round += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth_round = max(0, depth_round - 1)
            buf.append(ch)
            continue
        if ch == "[":
            depth_square += 1
            buf.append(ch)
            continue
        if ch == "]":
            depth_square = max(0, depth_square - 1)
            buf.append(ch)
            continue
        if ch == "{":
            depth_curly += 1
            buf.append(ch)
            continue
        if ch == "}":
            depth_curly = max(0, depth_curly - 1)
            buf.append(ch)
            continue
        if ch == "," and depth_round == 0 and depth_square == 0 and depth_curly == 0:
            token = "".join(buf).strip()
            if token:
                parts.append(token)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _extract_setup_return_names(app_js: str) -> set[str]:
    out: set[str] = set()
    setup_match = re.search(r"\bsetup\s*\([^)]*\)\s*{", app_js)
    if not setup_match:
        return out
    setup_open = app_js.find("{", setup_match.start())
    setup_block = _balanced_block(app_js, setup_open)
    if not setup_block:
        return out
    setup_body, _ = setup_block
    ret_match = re.search(r"\breturn\s*{", setup_body)
    if not ret_match:
        return out
    ret_open = setup_body.find("{", ret_match.start())
    ret_block = _balanced_block(setup_body, ret_open)
    if not ret_block:
        return out
    ret_body, _ = ret_block
    for entry in _split_top_level_csv(ret_body):
        token = re.sub(r"/\*.*?\*/", "", entry, flags=re.DOTALL)
        token = re.sub(r"//.*", "", token).strip()
        if not token or token.startswith("..."):
            continue
        key_match = re.match(r"^([A-Za-z_$][A-Za-z0-9_$]*)\s*:", token)
        if key_match:
            out.add(key_match.group(1))
            continue
        quoted_key_match = re.match(r"""^['"]([A-Za-z_$][A-Za-z0-9_$]*)['"]\s*:""", token)
        if quoted_key_match:
            out.add(quoted_key_match.group(1))
            continue
        short_match = re.match(r"^([A-Za-z_$][A-Za-z0-9_$]*)$", token)
        if short_match:
            out.add(short_match.group(1))
    return out


def _extract_template_literals(app_js: str) -> list[str]:
    literals: list[str] = []
    for match in re.finditer(r"template\s*:\s*(`[\s\S]*?`|'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")", app_js):
        raw = match.group(1).strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"`", "'", '"'}:
            literals.append(raw[1:-1])
    return literals


def _extract_expr_roots(expr: str) -> set[str]:
    cleaned = re.sub(r"`[\s\S]*?`|'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"", " ", expr)
    roots: set[str] = set()
    for token in re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", cleaned):
        if "." in token:
            # Ignore chained object access (e.g. dog.id) to avoid false positives.
            continue
        if token in _JS_KEYWORDS or token in _JS_GLOBALS or token in _VUE_GLOBALS:
            continue
        roots.add(token)
    return roots


def _check_vue_bindings(index_html: str, app_js: str) -> list[str]:
    issues: list[str] = []
    returned_names = _extract_setup_return_names(app_js)
    if not returned_names:
        issues.append("Could not parse setup() return { ... } block in app.js.")
        return issues

    template_sources = [index_html] + _extract_template_literals(app_js)
    combined_templates = "\n\n".join([src for src in template_sources if src])

    aliases: set[str] = set()
    referenced: set[str] = set()

    for expr in re.findall(r"v-for\s*=\s*['\"]([^'\"]+)['\"]", combined_templates):
        parts = re.split(r"\s+(?:in|of)\s+", expr, maxsplit=1)
        if len(parts) == 2:
            lhs, rhs = parts
            lhs = lhs.strip().strip("()")
            for alias in [x.strip() for x in lhs.split(",")]:
                if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", alias):
                    aliases.add(alias)
            referenced.update(_extract_expr_roots(rhs))
        else:
            referenced.update(_extract_expr_roots(expr))

    expr_patterns = [
        r"{{\s*(.*?)\s*}}",
        r"v-model\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:v-bind:[\w-]+|:[\w-]+)\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:v-if|v-else-if|v-show)\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:@[\w-]+|v-on:[\w-]+)\s*=\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in expr_patterns:
        for expr in re.findall(pattern, combined_templates, re.DOTALL):
            referenced.update(_extract_expr_roots(expr))

    unresolved = sorted(name for name in referenced if name not in returned_names and name not in aliases)
    for name in unresolved:
        issues.append(f"Vue binding references '{name}' but setup() does not return it.")

    has_js_template = bool(re.search(r"\btemplate\s*:", app_js))
    app_div_match = re.search(r"<div[^>]*id=['\"]app['\"][^>]*>([\s\S]*?)</div>", index_html, re.IGNORECASE)
    has_inline_template = False
    if app_div_match:
        inner = re.sub(r"<!--[\s\S]*?-->", "", app_div_match.group(1)).strip()
        has_inline_template = bool(inner)
    if has_js_template and has_inline_template:
        issues.append("Template conflict: index.html has inline #app markup and app.js also defines template:.")

    return issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _trim(text: str, max_chars: int) -> str:
    body = str(text or "").strip()
    if len(body) <= max_chars:
        return body
    cut = body[:max_chars].rsplit("\n", 1)[0].strip()
    return cut or body[:max_chars]


_CODE_FENCE_RE = re.compile(r"```(?:python|sql|html|javascript|js|vue)?\n(.*?)```", re.DOTALL)


def _extract_largest_block(text: str) -> str:
    blocks = _CODE_FENCE_RE.findall(str(text or ""))
    if not blocks:
        return str(text or "").strip()
    return max(blocks, key=len).strip()


def _extract_named_block(text: str, extensions: tuple[str, ...]) -> str:
    """Extract first code block matching any of the given language hints."""
    pattern = re.compile(
        r"```(?:" + "|".join(extensions) + r")?\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    blocks = pattern.findall(str(text or ""))
    if not blocks:
        return _extract_largest_block(text)
    return max(blocks, key=len).strip()


def _py_compile_check(code: str) -> tuple[bool, str]:
    """Run py_compile on code string. Returns (ok, error_text)."""
    tmp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp = f.name
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", tmp],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout or "syntax error").strip()
    except subprocess.TimeoutExpired:
        return False, "[py_compile timed out]"
    except Exception as exc:
        return False, str(exc)
    finally:
        if tmp:
            try:
                Path(tmp).unlink()
            except Exception:
                pass


def _import_smoke_check(flask_code: str, db_py: str, schema_sql: str) -> tuple[bool, str]:
    """Write a temp app package and verify `import app` succeeds."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "app.py").write_text(flask_code, encoding="utf-8")
            (tmp_path / "db.py").write_text(db_py, encoding="utf-8")
            (tmp_path / "schema.sql").write_text(schema_sql, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-c", "import app"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, ""
            err = (result.stderr or result.stdout or "import smoke check failed").strip()
            # Missing third-party packages are environment/setup issues and are already
            # reported by dependency checks; do not force code regeneration for them.
            miss = re.search(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", err)
            if miss:
                mod = miss.group(1).split(".")[0].strip()
                if mod in {"flask", "flask_cors"}:
                    return True, ""
            return False, err
    except subprocess.TimeoutExpired:
        return False, "[import smoke check timed out]"
    except Exception as exc:
        return False, str(exc)


def _runtime_smoke_check(project_dir: Path, spec: AppSpec | None) -> tuple[bool, str]:
    """Run a short Flask runtime smoke test against /api/health and one spec GET route."""
    if os.environ.get("OATHWEAVER_SKIP_RUNTIME_SMOKE", "").strip() == "1":
        return True, ""

    proc: subprocess.Popen[str] | None = None
    fail_reason = ""
    stderr_tail = ""
    stdout_tail = ""
    started = time.monotonic()
    max_runtime_sec = 15.0

    def _remaining() -> float:
        return max(0.1, max_runtime_sec - (time.monotonic() - started))

    def _get_json(url: str) -> tuple[int, Any, str]:
        req = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(req, timeout=min(3.0, _remaining())) as response:
            status = int(getattr(response, "status", response.getcode()))
            raw = response.read().decode("utf-8", errors="replace")
        parsed: Any
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"Invalid JSON response from {url}: {exc}. Body={raw[:800]}") from exc
        return status, parsed, raw

    try:
        if _remaining() <= 0:
            fail_reason = "Runtime smoke timed out before startup."
            return False, fail_reason

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "flask",
                "--app",
                "app",
                "run",
                "--no-debugger",
                "--no-reload",
                "--port",
                str(port),
            ],
            cwd=str(project_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )

        ready = False
        for _ in range(25):
            if _remaining() <= 0:
                break
            if proc.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    ready = True
                    break
            except OSError:
                time.sleep(0.2)

        if not ready:
            fail_reason = "Runtime smoke failed: Flask server did not become ready within 5s."
        if not fail_reason:
            health_url = f"http://127.0.0.1:{port}/api/health"
            try:
                status, payload, _raw = _get_json(health_url)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
                fail_reason = f"Runtime smoke failed: /api/health returned HTTP {exc.code}. Body={body[:800]}"
            except Exception as exc:
                fail_reason = f"Runtime smoke failed: /api/health request error: {exc}"

            if not fail_reason and status != 200:
                fail_reason = f"Runtime smoke failed: /api/health returned status {status}, expected 200."
            if not fail_reason and not isinstance(payload, dict):
                fail_reason = "Runtime smoke failed: /api/health payload is not a JSON object."
            if not fail_reason and payload.get("item", {}).get("status") != "ok":
                fail_reason = (
                    "Runtime smoke failed: /api/health payload shape mismatch; "
                    "expected {'item': {'status': 'ok'}}."
                )

        if not fail_reason:
            spec_get_path = ""
            if spec is not None:
                for route in spec.routes:
                    if str(route.method).upper() == "GET" and "<int:id>" not in str(route.path):
                        spec_get_path = str(route.path).strip()
                        if spec_get_path.startswith("/api/"):
                            break
                        spec_get_path = ""
            if spec_get_path:
                route_url = f"http://127.0.0.1:{port}{spec_get_path}"
                try:
                    route_status, route_payload, _ = _get_json(route_url)
                except urllib.error.HTTPError as exc:
                    body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
                    fail_reason = (
                        f"Runtime smoke failed: {spec_get_path} returned HTTP {exc.code}. "
                        f"Body={body[:800]}"
                    )
                except Exception as exc:
                    fail_reason = f"Runtime smoke failed: {spec_get_path} request error: {exc}"

                if not fail_reason and route_status != 200:
                    fail_reason = (
                        f"Runtime smoke failed: {spec_get_path} returned status {route_status}, expected 200."
                    )
                if not fail_reason and not isinstance(route_payload, dict):
                    fail_reason = f"Runtime smoke failed: {spec_get_path} payload is not a JSON object."
                if not fail_reason and ("items" not in route_payload or "meta" not in route_payload):
                    fail_reason = (
                        f"Runtime smoke failed: {spec_get_path} payload shape mismatch; "
                        "expected {'items': [...], 'meta': {...}}."
                    )
                if not fail_reason and not isinstance(route_payload.get("items"), list):
                    fail_reason = f"Runtime smoke failed: {spec_get_path} 'items' is not a list."
                if not fail_reason and not isinstance(route_payload.get("meta"), dict):
                    fail_reason = f"Runtime smoke failed: {spec_get_path} 'meta' is not an object."

        if not fail_reason and _remaining() <= 0:
            fail_reason = "Runtime smoke failed: exceeded 15s runtime budget."
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        proc.kill()
                out, err = proc.communicate(timeout=1)
                stdout_tail = str(out or "")[-3000:]
                stderr_tail = str(err or "")[-4000:]
            except Exception:
                pass
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass

    if fail_reason and stderr_tail:
        fail_reason = f"{fail_reason}\n\n[flask stderr]\n{stderr_tail}"
    elif fail_reason and stdout_tail:
        fail_reason = f"{fail_reason}\n\n[flask stdout]\n{stdout_tail}"

    if fail_reason and "No module named 'flask'" in fail_reason:
        # Environment-level missing dependency (handled by dependency checks).
        return (True, "")
    return (not fail_reason), fail_reason


def _fix_python(
    client: OllamaClient,
    code: str,
    error: str,
    question: str,
    cancel_checker: Callable[[], bool] | None,
) -> str:
    if callable(cancel_checker):
        try:
            if cancel_checker():
                return code
        except Exception:
            pass
    system_prompt = (
        "You are a Python debugging agent. "
        "Fix the syntax or import error in the code. "
        "Return the complete corrected Python file in a ```python block. "
        "Do not truncate. No explanations outside the code block."
    )
    user_prompt = (
        f"App request: {question}\n\n"
        f"Code with error:\n```python\n{code}\n```\n\n"
        f"Error:\n{error}\n\n"
        "Return the complete corrected Python code."
    )
    try:
        result = client.chat(
            model="qwen2.5-coder:7b",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            num_ctx=20480,
            think=False,
            timeout=300,
            retry_attempts=3,
            retry_backoff_sec=1.5,
        )
        fixed = _extract_named_block(str(result or ""), ("python",))
        return fixed if fixed.strip() else code
    except Exception:
        return code


def _chat(
    client: OllamaClient,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    num_ctx: int = 16384,
    timeout: int = 360,
) -> str:
    try:
        result = client.chat(
            model="qwen2.5-coder:7b",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            num_ctx=num_ctx,
            think=False,
            timeout=timeout,
            retry_attempts=4,
            retry_backoff_sec=1.5,
        )
        return str(result or "").strip()
    except Exception as exc:
        return f"[Model call failed: {exc}]"


# ---------------------------------------------------------------------------
# Extend mode: find an existing build to extend rather than rebuild from scratch
# ---------------------------------------------------------------------------

def _find_existing_app(repo_root: Path, project_slug: str) -> dict[str, str]:
    """Find the most recent _app/ build for this project and read key source files.

    Returns a dict of {relative_path: content}. Empty dict means no prior build found.
    Files read: app.py, schema.sql, db.py, templates/index.html, static/app.js, static/styles.css.
    """
    impl_dir = repo_root / "Projects" / project_slug / "implementation"
    if not impl_dir.exists():
        return {}
    app_dirs = sorted(
        [d for d in impl_dir.iterdir() if d.is_dir() and d.name.endswith("_app")],
        key=lambda d: d.name,
        reverse=True,  # most recent first (ISO timestamp prefix sorts lexicographically)
    )
    if not app_dirs:
        return {}
    latest = app_dirs[0]
    found: dict[str, str] = {}
    for rel in ("app.py", "schema.sql", "db.py", "templates/index.html", "static/app.js", "static/styles.css"):
        path = latest / rel
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    found[rel] = content
            except Exception:
                pass
    if found:
        found["__source_dir__"] = latest.name  # record which build we're extending
        found["__source_path__"] = str(latest)
    return found


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _step_db_architect(
    client: OllamaClient,
    question: str,
    research_knowledge: str,
    existing_schema: str = "",
    existing_db_py: str = "",
) -> tuple[str, str]:
    """Returns (schema_sql, db_helpers_py)."""
    if existing_schema:
        system_prompt = (
            f"Today: {_today()}. "
            "You are a SQLite database architect EXTENDING an existing app. "
            "Review the existing schema and add only the tables or columns the new feature requires. "
            "Do NOT remove or rename existing tables or columns — only add. "
            "Follow these patterns exactly:\n\n" + _SQLITE_PATTERNS + "\n\n" + _SQLITE_GOTCHAS + "\n\n"
            "Output TWO code blocks:\n"
            "1. A ```sql block with the COMPLETE updated schema.sql (existing + new tables).\n"
            "2. A ```python block with the COMPLETE updated db.py (keep existing helpers, add new ones only if needed).\n"
            "Nothing else."
        )
        user_prompt = (
            f"New feature to add: {question}\n\n"
            f"Existing schema.sql (keep all — only add what the new feature requires):\n"
            f"```sql\n{_trim(existing_schema, 3000)}\n```\n\n"
            f"Existing db.py (keep unchanged unless a new helper is needed):\n"
            f"```python\n{_trim(existing_db_py, 2000)}\n```\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 2000) or '(none)'}\n\n"
            "Output the complete updated schema.sql and db.py."
        )
    else:
        system_prompt = (
            f"Today: {_today()}. "
            "You are a SQLite database architect. Design a complete schema and Flask db-helper module. "
            "Follow these patterns exactly:\n\n" + _SQLITE_PATTERNS + "\n\n" + _SQLITE_GOTCHAS + "\n\n"
            "Output TWO code blocks:\n"
            "1. A ```sql block with schema.sql — CREATE TABLE statements first, then optional INSERT seed statements.\n"
            "2. A ```python block with db.py — get_db(), close_db(), init_db() only.\n"
            "Nothing else."
        )
        user_prompt = (
            f"App to build: {question}\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 2500) or '(none)'}\n\n"
            "Design a minimal but complete SQLite schema for this app."
        )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.15, num_ctx=16384)

    sql_match = re.search(r"```sql\n(.*?)```", raw, re.DOTALL)
    py_match = re.search(r"```python\n(.*?)```", raw, re.DOTALL)
    schema_sql = sql_match.group(1).strip() if sql_match else _extract_largest_block(raw)
    db_py = py_match.group(1).strip() if py_match else ""

    if not db_py:
        db_py = (
            "import sqlite3\nfrom flask import g\n\nDATABASE = 'app.db'\n\n"
            "def get_db():\n    if 'db' not in g:\n        g.db = sqlite3.connect(DATABASE)\n"
            "        g.db.row_factory = sqlite3.Row\n        g.db.execute('PRAGMA foreign_keys = ON')\n"
            "    return g.db\n\n"
            "@app.teardown_appcontext\ndef close_db(e=None):\n    db = g.pop('db', None)\n"
            "    if db is not None:\n        db.close()\n\n"
            "def init_db():\n    with app.app_context():\n        db = get_db()\n"
            "        with open('schema.sql') as f:\n            db.executescript(f.read())\n"
            "        db.commit()\n"
        )
    return schema_sql, db_py


def _step_api_implementer(
    client: OllamaClient,
    question: str,
    schema_sql: str,
    db_py: str,
    research_knowledge: str,
    cancel_checker: Callable[[], bool] | None,
    progress_callback: Callable | None,
    existing_flask_code: str = "",
) -> str:
    def _prog(stage: str, detail: dict | None = None) -> None:
        if callable(progress_callback):
            try:
                progress_callback(stage, detail or {})
            except Exception:
                pass

    if existing_flask_code:
        system_prompt = (
            f"Today: {_today()}. "
            "You are a Flask API developer EXTENDING an existing app. "
            "Add or modify ONLY the routes needed for the new feature. "
            "Keep ALL existing working routes exactly as-is — do not delete or rename them. "
            "Follow these patterns:\n\n"
            + _FLASK_PATTERNS + "\n\n" + _FLASK_GOTCHAS + "\n\n"
            + _SQLITE_PATTERNS + "\n\n" + _SQLITE_GOTCHAS + "\n\n"
            "Output ONE complete ```python block — the full updated app.py ready to run."
        )
        user_prompt = (
            f"New feature to add: {question}\n\n"
            f"Existing app.py (keep all existing routes — add/modify ONLY what the new feature needs):\n"
            f"```python\n{_trim(existing_flask_code, 5000)}\n```\n\n"
            f"Updated schema (schema.sql):\n```sql\n{_trim(schema_sql, 2000)}\n```\n\n"
            f"DB helper module (db.py):\n```python\n{_trim(db_py, 1500)}\n```\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 1200) or '(none)'}\n\n"
            "Output the complete updated app.py with all existing + new routes."
        )
    else:
        system_prompt = (
            f"Today: {_today()}. "
            "You are a Flask API implementer. Write a complete, runnable Flask app.py. "
            "Import and use get_db() from db.py — do not redefine database functions. "
            "Follow these patterns:\n\n"
            + _FLASK_PATTERNS + "\n\n" + _FLASK_GOTCHAS + "\n\n"
            + _SQLITE_PATTERNS + "\n\n" + _SQLITE_GOTCHAS + "\n\n"
            "Output ONE complete ```python block — the full app.py file ready to run. "
            "Include if __name__ == '__main__': app.run(debug=True) at the bottom."
        )
        user_prompt = (
            f"App to build: {question}\n\n"
            f"Database schema (schema.sql):\n```sql\n{_trim(schema_sql, 3000)}\n```\n\n"
            f"DB helper module (db.py — import from this, don't redefine):\n```python\n{_trim(db_py, 2000)}\n```\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 1800) or '(none)'}\n\n"
            "Write the complete Flask app.py with all routes implemented."
        )
    code = _extract_named_block(
        _chat(client, system_prompt, user_prompt, temperature=0.15, num_ctx=20480, timeout=480),
        ("python",),
    )

    # py_compile + import smoke checks with shared fix loop
    def _validate(candidate: str) -> tuple[bool, str]:
        ok_compile, compile_err = _py_compile_check(candidate)
        if not ok_compile:
            return False, compile_err
        ok_smoke, smoke_err = _import_smoke_check(candidate, db_py, schema_sql)
        if not ok_smoke:
            return False, smoke_err
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                (tmp_path / "app.py").write_text(candidate, encoding="utf-8")
                (tmp_path / "db.py").write_text(db_py, encoding="utf-8")
                (tmp_path / "schema.sql").write_text(schema_sql, encoding="utf-8")
                ok_runtime, runtime_err = _runtime_smoke_check(tmp_path, None)
                if not ok_runtime:
                    return False, runtime_err
        except Exception as exc:
            return False, f"Runtime smoke wrapper failed: {exc}"
        return True, ""

    ok, err = _validate(code)
    if not ok:
        for cycle in range(1, 3):
            _prog("app_api_fix_cycle", {"cycle": cycle, "error": err[:200]})
            if callable(cancel_checker):
                try:
                    if cancel_checker():
                        break
                except Exception:
                    pass
            code = _fix_python(client, code, err, question, cancel_checker)
            ok, err = _validate(code)
            if ok:
                _prog("app_api_fix_passed", {"cycle": cycle})
                break
    return code


def _step_vue_architect(
    client: OllamaClient,
    question: str,
    flask_code: str,
    research_knowledge: str = "",
) -> str:
    """Plan Vue 3 component structure based on actual Flask routes."""
    system_prompt = (
        f"Today: {_today()}. "
        "You are a Vue 3 frontend architect. Given a Flask backend, plan the frontend. "
        "List every Flask API route, then map each to a Vue interaction (fetch call, form, list render). "
        "Output a concise component plan — no code yet, just structure and data flow.\n\n"
        + _VUE3_PATTERNS + "\n\n" + _VUE3_GOTCHAS
    )
    # Extract just the route definitions from flask_code to save context
    route_lines = [l for l in flask_code.splitlines() if "@app.route" in l or "def " in l]
    route_summary = "\n".join(route_lines[:40])
    user_prompt = (
        f"App: {question}\n\n"
        f"Flask routes defined:\n{route_summary}\n\n"
        f"Research knowledge:\n{_trim(research_knowledge, 1600) or '(none)'}\n\n"
        "Plan the Vue 3 component structure and data flow. Be specific about which API calls go where."
    )
    return _chat(client, system_prompt, user_prompt, temperature=0.2, num_ctx=16384)


def _step_vue_implementer(
    client: OllamaClient,
    question: str,
    schema_sql: str,
    flask_code: str,
    vue_plan: str,
    research_knowledge: str = "",
    existing_app_js: str = "",
    existing_index_html: str = "",
) -> tuple[str, str]:
    """Returns (index_html, app_js)."""
    route_lines = [l for l in flask_code.splitlines() if "@app.route" in l or "def " in l]
    route_summary = "\n".join(route_lines[:40])

    # app.js
    if existing_app_js:
        system_prompt_js = (
            f"Today: {_today()}. "
            "You are a Vue 3 frontend developer EXTENDING an existing app.js. "
            "Add new state, methods, and template sections for the new feature. "
            "Keep ALL existing state and methods unchanged — do not remove or rename them. "
            "Follow these patterns:\n\n" + _VUE3_PATTERNS + "\n\n" + _VUE3_GOTCHAS + "\n\n"
            "Output ONE complete ```javascript block — the full updated app.js."
        )
        user_prompt_js = (
            f"New feature to add: {question}\n\n"
            f"Extension plan:\n{_trim(vue_plan, 1500)}\n\n"
            f"All Flask API routes (including new ones):\n{route_summary}\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 1200) or '(none)'}\n\n"
            f"Existing app.js (keep all existing code — add new feature sections):\n"
            f"```javascript\n{_trim(existing_app_js, 4000)}\n```\n\n"
            "Output the complete updated app.js."
        )
    else:
        system_prompt_js = (
            f"Today: {_today()}. "
            "You are a Vue 3 frontend implementer. Write a complete app.js file. "
            "Follow these patterns exactly:\n\n" + _VUE3_PATTERNS + "\n\n" + _VUE3_GOTCHAS + "\n\n"
            "Rules:\n"
            "- Use Vue 3 global build (CDN) — const { createApp, ref, reactive, computed, onMounted } = Vue;\n"
            "- All API calls use fetch() — no axios.\n"
            "- Handle loading and error states for every fetch.\n"
            "- Mount to #app.\n"
            "- Output ONE complete ```javascript block."
        )
        user_prompt_js = (
            f"App: {question}\n\n"
            f"Frontend plan:\n{_trim(vue_plan, 2000)}\n\n"
            f"Flask API routes available:\n{route_summary}\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 1200) or '(none)'}\n\n"
            "Write the complete app.js — all state, API calls, and template logic."
        )
    app_js_raw = _chat(client, system_prompt_js, user_prompt_js, temperature=0.3, num_ctx=20480, timeout=480)
    app_js = _extract_named_block(app_js_raw, ("javascript", "js"))

    # index.html
    if existing_index_html:
        system_prompt_html = (
            f"Today: {_today()}. "
            "You are a Vue 3 HTML template developer EXTENDING an existing index.html. "
            "Add new template markup inside #app for the new feature. "
            "Keep ALL existing markup, CDN script tags, and stylesheet links unchanged. "
            "Output ONE complete ```html block — the full updated index.html."
        )
        user_prompt_html = (
            f"New feature to add: {question}\n\n"
            f"Updated app.js (for reference — use the same state variables and methods):\n"
            f"{_trim(app_js, 2000)}\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 1000) or '(none)'}\n\n"
            f"Existing index.html (keep all existing markup — add new sections for the feature):\n"
            f"```html\n{_trim(existing_index_html, 3000)}\n```\n\n"
            "Output the complete updated index.html."
        )
    else:
        system_prompt_html = (
            f"Today: {_today()}. "
            "You are a Vue 3 HTML template writer. Write the index.html entry point. "
            "Follow these patterns:\n\n" + _VUE3_PATTERNS + "\n\n" + _VUE3_GOTCHAS + "\n\n"
            "Rules:\n"
            "- Load Vue 3 from CDN: https://unpkg.com/vue@3/dist/vue.global.js\n"
            "- Load /static/app.js after Vue.\n"
            "- Link /static/styles.css.\n"
            "- The #app div contains the full template markup (inline, not in app.js).\n"
            "- Use v-bind, v-on shorthand (: and @).\n"
            "- Output ONE complete ```html block."
        )
        user_prompt_html = (
            f"App: {question}\n\n"
            f"Vue app.js structure:\n{_trim(app_js, 3000)}\n\n"
            f"Research knowledge:\n{_trim(research_knowledge, 1000) or '(none)'}\n\n"
            "Write the complete index.html with all template markup inside #app."
        )
    index_html = _extract_named_block(
        _chat(client, system_prompt_html, user_prompt_html, temperature=0.25, num_ctx=20480, timeout=360),
        ("html",),
    )
    vue_issues = _check_html_structure(index_html) + _check_vue_bindings(index_html, app_js)
    if vue_issues:
        issue_blob = "\n".join(f"- {msg}" for msg in vue_issues[:30])
        fix_js_system = (
            f"Today: {_today()}. "
            "You are a Vue 3 JavaScript fixer. Resolve every listed template/binding issue. "
            "Return the complete corrected app.js in one ```javascript block."
        )
        fix_js_user = (
            f"App: {question}\n\n"
            f"Issues to fix:\n{issue_blob}\n\n"
            f"Current app.js:\n```javascript\n{_trim(app_js, 5000)}\n```\n\n"
            f"Current index.html:\n```html\n{_trim(index_html, 3000)}\n```\n\n"
            "Return corrected app.js."
        )
        js_candidate = _extract_named_block(
            _chat(client, fix_js_system, fix_js_user, temperature=0.15, num_ctx=20480, timeout=360),
            ("javascript", "js"),
        )
        if js_candidate.strip():
            app_js = js_candidate

        fix_html_system = (
            f"Today: {_today()}. "
            "You are a Vue 3 HTML fixer. Resolve every listed structure/template issue while preserving valid markup. "
            "Return the complete corrected index.html in one ```html block."
        )
        fix_html_user = (
            f"App: {question}\n\n"
            f"Issues to fix:\n{issue_blob}\n\n"
            f"Updated app.js:\n```javascript\n{_trim(app_js, 5000)}\n```\n\n"
            f"Current index.html:\n```html\n{_trim(index_html, 3500)}\n```\n\n"
            "Return corrected index.html."
        )
        html_candidate = _extract_named_block(
            _chat(client, fix_html_system, fix_html_user, temperature=0.15, num_ctx=20480, timeout=360),
            ("html",),
        )
        if html_candidate.strip():
            index_html = html_candidate
    return index_html, app_js


def _step_integration_check(
    client: OllamaClient,
    question: str,
    flask_code: str,
    app_js: str,
    index_html: str,
    research_knowledge: str = "",
) -> str:
    system_prompt = (
        f"Today: {_today()}. "
        "You are an integration checker. Compare a Flask backend and Vue 3 frontend. "
        "Find SPECIFIC mismatches only:\n"
        "- API routes in Flask not called in app.js\n"
        "- fetch() calls in app.js to routes that don't exist in Flask\n"
        "- JSON field names that differ between Flask response and Vue template\n"
        "- Missing CORS setup\n"
        "- Missing error handling\n"
        "List each issue as: [FILE] ISSUE: fix instruction. "
        "If no issues, say 'Integration looks clean.' and stop."
    )
    # Compress for context
    route_lines = [l for l in flask_code.splitlines() if "@app.route" in l or "return jsonify" in l]
    fetch_lines = [l for l in app_js.splitlines() if "fetch(" in l or "await " in l]
    user_prompt = (
        f"App: {question}\n\n"
        f"Flask routes/returns:\n{chr(10).join(route_lines[:50])}\n\n"
        f"Vue fetch calls:\n{chr(10).join(fetch_lines[:50])}\n\n"
        f"HTML template (first 2000 chars):\n{index_html[:2000]}\n\n"
        f"Research knowledge:\n{_trim(research_knowledge, 1200) or '(none)'}"
    )
    return _chat(client, system_prompt, user_prompt, temperature=0.1, num_ctx=16384)


def _step_integration_fixer(
    client: OllamaClient,
    question: str,
    flask_code: str,
    app_js: str,
    integration_notes: str,
    cancel_checker: Callable[[], bool] | None,
) -> tuple[str, str]:
    """Apply integration_check findings to actual code. Returns (fixed_flask_code, fixed_app_js)."""

    def _is_cancelled() -> bool:
        if callable(cancel_checker):
            try:
                return bool(cancel_checker())
            except Exception:
                pass
        return False

    # Flask fixer pass
    if not _is_cancelled():
        system_prompt = (
            f"Today: {_today()}. "
            "You are a Flask integration fixer. You will receive a Flask app.py and a list of "
            "integration issues found by an automated checker. "
            "Fix ALL listed issues in the Flask code. "
            "Do not change working code — only fix what is listed.\n\n"
            + _FLASK_PATTERNS + "\n\n" + _FLASK_GOTCHAS + "\n\n"
            + _SQLITE_PATTERNS + "\n\n" + _SQLITE_GOTCHAS + "\n\n"
            "Return the complete corrected app.py in ONE ```python block. Do not truncate."
        )
        user_prompt = (
            f"App: {question}\n\n"
            f"Integration issues to fix:\n{_trim(integration_notes, 2000)}\n\n"
            f"Current app.py:\n```python\n{_trim(flask_code, 6000)}\n```\n\n"
            "Return the complete corrected app.py."
        )
        fixed_raw = _chat(client, system_prompt, user_prompt, temperature=0.1, num_ctx=20480, timeout=480)
        candidate = _extract_named_block(fixed_raw, ("python",))
        if candidate.strip():
            ok, err = _py_compile_check(candidate)
            if ok:
                flask_code = candidate
            else:
                # One more fix attempt
                flask_code = _fix_python(client, candidate, err, question, cancel_checker) or flask_code

    # Frontend fixer pass — runs after Flask so it can match any Flask changes
    if not _is_cancelled():
        route_lines = [l for l in flask_code.splitlines() if "@app.route" in l or "return jsonify" in l]
        route_summary = "\n".join(route_lines[:50])
        system_prompt = (
            f"Today: {_today()}. "
            "You are a Vue 3 frontend integration fixer. You will receive an app.js and a list of "
            "integration issues found by an automated checker. "
            "Fix ALL listed issues in the JavaScript. "
            "Ensure every fetch() URL matches an actual Flask route. "
            "Do not change working code — only fix what is listed.\n\n"
            + _VUE3_PATTERNS + "\n\n" + _VUE3_GOTCHAS + "\n\n"
            "Return the complete corrected app.js in ONE ```javascript block. Do not truncate."
        )
        user_prompt = (
            f"App: {question}\n\n"
            f"Integration issues to fix:\n{_trim(integration_notes, 2000)}\n\n"
            f"Updated Flask routes (after backend fix):\n{route_summary}\n\n"
            f"Current app.js:\n```javascript\n{_trim(app_js, 6000)}\n```\n\n"
            "Return the complete corrected app.js."
        )
        fixed_raw = _chat(client, system_prompt, user_prompt, temperature=0.1, num_ctx=20480, timeout=480)
        candidate = _extract_named_block(fixed_raw, ("javascript", "js"))
        if candidate.strip():
            app_js = candidate

    return flask_code, app_js


def _check_css_validity(css: str) -> list[str]:
    issues: list[str] = []
    for line_no, line in enumerate(css.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if re.search(r"\b(?:darken|lighten|saturate|desaturate)\s*\(", lowered):
            issues.append(f"Line {line_no}: SCSS color function found: {stripped[:140]}")
        mix_match = re.search(r"\bmix\s*\(([^)]*)\)", lowered)
        if mix_match and mix_match.group(1).count(",") >= 2:
            issues.append(f"Line {line_no}: SCSS-style mix() with more than two args: {stripped[:140]}")
        if re.search(r"@\s*(?:mixin|include|extend)\b", lowered):
            issues.append(f"Line {line_no}: SCSS directive found: {stripped[:140]}")
        if re.search(r"^\s*\$[A-Za-z0-9_-]+\s*:", line):
            issues.append(f"Line {line_no}: SCSS variable declaration found: {stripped[:140]}")
        if re.search(r"&\s*[.#:\[]", line):
            issues.append(f"Line {line_no}: Nested selector using '&' found: {stripped[:140]}")
    return issues


def _parse_feature_list(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    candidates = [text]
    bracket = re.search(r"\[[\s\S]*\]", text)
    if bracket:
        candidates.insert(0, bracket.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if not isinstance(parsed, list):
            continue
        out: list[str] = []
        seen: set[str] = set()
        for item in parsed:
            cleaned = re.sub(r"\s+", " ", str(item or "")).strip().strip(".,:;\"'")
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
        return out[:8]
    return []


def _check_feature_coverage(
    client: OllamaClient,
    question: str,
    schema_sql: str,
    flask_code: str,
    index_html: str,
    app_js: str,
) -> list[str]:
    system_prompt = (
        "Extract noun phrases from this build request that represent explicit trackable features or entities. "
        "Examples: milestones, daily goals, notes. "
        "Return JSON only: an array of 3-8 short feature names. "
        "Do not include inferred or implicit features."
    )
    user_prompt = f"Build request:\n{_trim(question, 1200)}\n\nReturn JSON array only."
    raw = _chat(client, system_prompt, user_prompt, temperature=0.1, num_ctx=8192, timeout=180)
    features = _parse_feature_list(raw)
    if not features:
        return []

    schema_low = schema_sql.lower()
    flask_low = flask_code.lower()
    html_low = index_html.lower()
    js_low = app_js.lower()
    issues: list[str] = []
    for feature in features:
        needle = feature.lower()
        in_backend = needle in schema_low or needle in flask_low
        in_frontend = needle in html_low or needle in js_low
        if not in_backend:
            issues.append(f"Feature '{feature}' missing from backend")
        if not in_frontend:
            issues.append(f"Feature '{feature}' missing from frontend")
    return issues


def _step_css_writer(
    client: OllamaClient,
    question: str,
    index_html: str,
    existing_css: str = "",
) -> str:
    """Generate (or extend) styles.css from HTML structure. Returns css_str."""
    # Extract class names and IDs from the (updated) HTML
    classes = re.findall(r'class="([^"]+)"', index_html)
    all_classes = set()
    for cls_attr in classes:
        for cls in cls_attr.split():
            all_classes.add(f".{cls}")
    ids = re.findall(r'id="([^"]+)"', index_html)
    all_ids = {f"#{i}" for i in ids if i != "app"}
    selectors = sorted(all_classes | all_ids)
    selector_list = "\n".join(selectors[:80]) if selectors else "(no classes/IDs found)"

    if existing_css:
        system_prompt = (
            f"Today: {_today()}. "
            "You are a CSS developer EXTENDING an existing stylesheet. "
            "Add new selectors for the new feature's HTML elements. "
            "Keep ALL existing CSS rules exactly as-is — only append new rules. "
            "Match the existing color scheme and spacing conventions. "
            "Return ONE complete ```css block — existing rules first, new rules appended."
        )
        user_prompt = (
            f"New feature added: {question}\n\n"
            f"All selectors in updated index.html (new ones need styles):\n{selector_list}\n\n"
            f"Existing styles.css (keep all — add new selectors for the new feature):\n"
            f"```css\n{_trim(existing_css, 4000)}\n```\n\n"
            f"Updated HTML structure (for layout reference):\n{_trim(index_html, 2000)}\n\n"
            "Output the complete updated styles.css."
        )
    else:
        system_prompt = (
            f"Today: {_today()}. "
            "You are a CSS designer. Write a complete, professional styles.css for a Flask + Vue 3 web app. "
            "Requirements:\n"
            "1. CSS custom properties at :root for color scheme (primary, secondary, background, surface, text, border, error).\n"
            "2. Basic reset: *, *::before, *::after { box-sizing: border-box; } body margin: 0.\n"
            "3. Layout: flexbox or grid matching the HTML structure.\n"
            "4. Navigation/header styles if present.\n"
            "5. Form styles: input, select, textarea, button — clean and usable.\n"
            "6. Table styles if tables are used.\n"
            "7. Loading spinner or skeleton state for .loading class.\n"
            "8. Error message style for .error class.\n"
            "9. Responsive breakpoint at 768px using @media.\n"
            "10. Style every class and ID selector listed — do not leave them unstyled.\n"
            "Return ONE complete ```css block. Professional quality, ready to use."
        )
        user_prompt = (
            f"App: {question}\n\n"
            f"Selectors found in index.html:\n{selector_list}\n\n"
            f"HTML structure (for layout reference):\n{_trim(index_html, 4000)}\n\n"
            "Write the complete styles.css."
        )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.3, num_ctx=16384, timeout=360)
    css_block = re.search(r"```(?:css)?\n(.*?)```", raw, re.DOTALL)
    css_out = ""
    if css_block:
        css_out = css_block.group(1).strip()
    else:
        # If no fenced block, return raw (model may have returned plain CSS)
        cleaned = raw.strip()
        if cleaned.startswith(":root") or cleaned.startswith("/*") or cleaned.startswith("*"):
            css_out = cleaned
        else:
            css_out = "/* Add your styles here */\nbody { font-family: system-ui, sans-serif; margin: 0; }\n"

    css_issues = _check_css_validity(css_out)
    if not css_issues:
        return css_out

    fix_system_prompt = (
        f"Today: {_today()}. "
        "You are a CSS fixer. Convert stylesheet content to plain CSS only. "
        "No SCSS functions, no nested selectors, no directives, no SCSS variables. "
        "If a darken/lighten-style effect is needed, use color-mix(in srgb, ... ) or precomputed hex values. "
        "Return one complete ```css block."
    )
    fix_user_prompt = (
        f"App: {question}\n\n"
        f"Issues to fix:\n- " + "\n- ".join(css_issues[:25]) + "\n\n"
        f"Current stylesheet:\n```css\n{_trim(css_out, 6000)}\n```\n\n"
        "Return corrected plain CSS."
    )
    fixed_raw = _chat(client, fix_system_prompt, fix_user_prompt, temperature=0.15, num_ctx=16384, timeout=360)
    fixed_block = re.search(r"```(?:css)?\n(.*?)```", fixed_raw, re.DOTALL)
    fixed_css = fixed_block.group(1).strip() if fixed_block else fixed_raw.strip()
    return fixed_css if fixed_css else css_out


def _step_readme(
    client: OllamaClient,
    question: str,
    schema_sql: str,
    flask_code: str,
    research_knowledge: str = "",
) -> str:
    # Extract imports to infer pip requirements
    import_lines = [l.strip() for l in flask_code.splitlines()
                    if l.strip().startswith(("import ", "from ")) and "flask" in l.lower()]
    system_prompt = (
        f"Today: {_today()}. "
        "Write a concise README.md for this Flask + Vue 3 + SQLite app. "
        "Include: Project description, Prerequisites, Installation, Database setup, "
        "Running the app, API endpoints list, File structure. "
        "Use markdown. Be practical and specific."
    )
    user_prompt = (
        f"App: {question}\n\n"
        f"Flask imports (infer pip requirements from these):\n{chr(10).join(import_lines)}\n\n"
        f"Schema:\n```sql\n{_trim(schema_sql, 1500)}\n```\n\n"
        f"Research knowledge:\n{_trim(research_knowledge, 1000) or '(none)'}\n\n"
        "Write the README.md."
    )
    return _chat(client, system_prompt, user_prompt, temperature=0.3, num_ctx=12288)


# ---------------------------------------------------------------------------
# Canon helpers
# ---------------------------------------------------------------------------

_CANON_VERSION = "web_app_v1"


def _slot_paths(app_dir: Path) -> dict[str, Path]:
    return {
        "app_py": app_dir / "app.py",
        "schema_sql": app_dir / "schema.sql",
        "db_py": app_dir / "db.py",
        "index_html": app_dir / "templates" / "index.html",
        "app_js": app_dir / "static" / "app.js",
        "styles_css": app_dir / "static" / "styles.css",
        "readme_md": app_dir / "README.md",
    }


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _default_app_spec(question: str) -> AppSpec:
    noun = re.sub(r"[^a-z0-9]+", "_", question.lower()).strip("_")
    base = noun.split("_")[0] if noun else "record"
    singular = base if re.match(r"^[a-z][a-z0-9_]*$", base or "") else "record"
    plural = singular if singular.endswith("s") else f"{singular}s"
    payload = {
        "app_name": f"{singular.title()} Tracker",
        "feature_summary": str(question or "").strip() or "Generated app feature",
        "entities": [
            {
                "name": singular,
                "primary_key": "id",
                "fields": [
                    {"name": "name", "type": "str", "required": True},
                    {"name": "notes", "type": "str", "required": False},
                    {"name": "created_at", "type": "datetime", "required": False},
                ],
            }
        ],
        "routes": [
            {"method": "GET", "path": f"/api/{plural}", "handler_name": f"list_{plural}", "entity": singular, "summary": f"List {plural}"},
            {"method": "POST", "path": f"/api/{plural}", "handler_name": f"create_{singular}", "entity": singular, "summary": f"Create {singular}"},
            {"method": "GET", "path": f"/api/{plural}/<int:id>", "handler_name": f"get_{singular}", "entity": singular, "summary": f"Get {singular}"},
            {"method": "PUT", "path": f"/api/{plural}/<int:id>", "handler_name": f"update_{singular}", "entity": singular, "summary": f"Update {singular}"},
            {"method": "DELETE", "path": f"/api/{plural}/<int:id>", "handler_name": f"delete_{singular}", "entity": singular, "summary": f"Delete {singular}"},
        ],
        "views": [
            {"name": "main-panel", "entity": singular, "purpose": f"Display and manage {plural}"}
        ],
        "notes": "",
    }
    return AppSpec.model_validate(payload)


def _step_spec_generator(
    client: OllamaClient,
    question: str,
    research_knowledge: str,
    existing_context: str = "",
) -> AppSpec:
    system_prompt = (
        f"Today: {_today()}. You generate structured AppSpec JSON for a Flask+Vue+SQLite app.\n"
        "Return one JSON object only matching fields:\n"
        "app_name, feature_summary, entities[], routes[], views[], notes.\n"
        "Use route paths /api/<plural> and /api/<plural>/<int:id>.\n"
        "Use handler_name snake_case.\n"
        "Use view names kebab-case."
    )
    user_prompt = (
        f"Build request:\n{_trim(question, 1400)}\n\n"
        f"Research context:\n{_trim(research_knowledge, 2000) or '(none)'}\n\n"
        f"Existing app context:\n{_trim(existing_context, 1600) or '(none)'}"
    )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.15, num_ctx=16384, timeout=300)
    try:
        return parse_spec_text(raw)
    except Exception:
        return _default_app_spec(question)


def _step_scaffold_copy(*, target_dir: Path, existing: dict[str, str]) -> tuple[str, str]:
    source_path = str(existing.get("__source_path__", "")).strip()
    if source_path:
        source_dir = Path(source_path)
        canon_marker = source_dir / ".canon-version"
        if canon_marker.exists():
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
            return "extend_canon", ""

    copy_scaffold(_CANON_VERSION, target_dir)
    if source_path:
        return "migrate_legacy", f"Legacy app detected: {Path(source_path).name}"
    return "new_canon", ""


def _step_db_architect_slots(
    client: OllamaClient,
    question: str,
    spec: AppSpec,
    research_knowledge: str,
    existing_tables: str = "",
    existing_seeds: str = "",
) -> tuple[str, str]:
    system_prompt = (
        f"Today: {_today()}. Fill schema.sql canon slots.\n"
        "Return JSON only: {\"tables\": \"...\", \"seeds\": \"...\"}.\n"
        "tables: SQL DDL only. Include indexes for foreign keys.\n"
        "seeds: SQL INSERT statements only.\n"
        "Never include markdown fences."
    )
    user_prompt = (
        f"Request: {question}\n\n"
        f"Spec:\n{spec_to_json(spec)}\n\n"
        f"Research context:\n{_trim(research_knowledge, 1200) or '(none)'}\n\n"
        f"Existing tables slot:\n{_trim(existing_tables, 1500) or '(none)'}\n\n"
        f"Existing seeds slot:\n{_trim(existing_seeds, 1000) or '(none)'}"
    )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.1, num_ctx=16384)
    parsed = _parse_json_object(raw)
    tables = str(parsed.get("tables", "")).strip() or existing_tables
    seeds = str(parsed.get("seeds", "")).strip() or existing_seeds
    if not tables:
        first = spec.entities[0]
        table_name = first.name if first.name.endswith("s") else f"{first.name}s"
        tables = (
            f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    name TEXT NOT NULL,\n"
            "    notes TEXT,\n"
            "    created_at TEXT DEFAULT (datetime('now', 'utc'))\n"
            ");"
        )
    return tables.strip(), seeds.strip()


def _step_api_slot_fill(
    client: OllamaClient,
    question: str,
    spec: AppSpec,
    research_knowledge: str,
    current_imports: str,
    current_routes: str,
    issue_notes: str = "",
) -> tuple[str, str]:
    system_prompt = (
        f"Today: {_today()}. Fill canon app.py slots.\n"
        "Output JSON only with keys: imports_feature, routes_feature.\n"
        "Use envelope helpers only: ok_item, ok_items, err.\n"
        "Do not redefine app, get_db, or envelope helpers.\n"
        "Route methods and paths must match spec."
    )
    user_prompt = (
        f"Request: {question}\n\n"
        f"Spec:\n{spec_to_json(spec)}\n\n"
        f"Research context:\n{_trim(research_knowledge, 1200) or '(none)'}\n\n"
        f"Current imports-feature slot:\n{_trim(current_imports, 1000) or '(empty)'}\n\n"
        f"Current routes-feature slot:\n{_trim(current_routes, 2600) or '(empty)'}\n\n"
        f"Issues to fix:\n{_trim(issue_notes, 1400) or '(none)'}"
    )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.12, num_ctx=20480, timeout=420)
    parsed = _parse_json_object(raw)
    imports_slot = str(parsed.get("imports_feature", "")).strip()
    routes_slot = str(parsed.get("routes_feature", "")).strip()
    if not routes_slot:
        entity = spec.entities[0].name
        table_name = entity if entity.endswith("s") else f"{entity}s"
        routes_slot = (
            f"@app.get(\"/api/{table_name}\")\n"
            f"def list_{table_name}():\n"
            f"    \"\"\"List {table_name}.\"\"\"\n"
            f"    db = get_db()\n"
            f"    rows = db.execute(\"SELECT * FROM {table_name} ORDER BY id DESC\").fetchall()\n"
            "    return ok_items([row_to_dict(row) for row in rows])"
        )
    return imports_slot, routes_slot


def _step_vue_architect_spec(
    client: OllamaClient,
    question: str,
    spec: AppSpec,
    research_knowledge: str,
) -> str:
    system_prompt = (
        f"Today: {_today()}. Plan Vue interaction flow from an AppSpec.\n"
        "Return concise markdown: data model, user actions, fetch mapping."
    )
    user_prompt = (
        f"Request: {question}\n\n"
        f"Spec:\n{spec_to_json(spec)}\n\n"
        f"Research context:\n{_trim(research_knowledge, 1000) or '(none)'}"
    )
    return _chat(client, system_prompt, user_prompt, temperature=0.2, num_ctx=12288, timeout=240)


def _step_vue_slot_fill(
    client: OllamaClient,
    question: str,
    spec: AppSpec,
    vue_plan: str,
    research_knowledge: str,
    current_slots: dict[str, str],
    issue_notes: str = "",
) -> dict[str, str]:
    system_prompt = (
        f"Today: {_today()}. Fill canon Vue slots for app.js and index.html.\n"
        "Return JSON only with keys:\n"
        "state, methods, computed, on_mounted, view_feature, head_feature.\n"
        "Match app.py route names and envelope response shape.\n"
        "Do not include markdown fences."
    )
    user_prompt = (
        f"Request: {question}\n\n"
        f"Spec:\n{spec_to_json(spec)}\n\n"
        f"Vue plan:\n{_trim(vue_plan, 1800)}\n\n"
        f"Research context:\n{_trim(research_knowledge, 1000) or '(none)'}\n\n"
        f"Current slots JSON:\n{json.dumps(current_slots, ensure_ascii=False, indent=2)[:4000]}\n\n"
        f"Issues to fix:\n{_trim(issue_notes, 1200) or '(none)'}"
    )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.2, num_ctx=24576, timeout=420)
    parsed = _parse_json_object(raw)
    output: dict[str, str] = {}
    for key in ("state", "methods", "computed", "on_mounted", "view_feature", "head_feature"):
        value = str(parsed.get(key, "")).strip()
        output[key] = value if value else str(current_slots.get(key, "")).strip()
    return output


def _step_css_slot_fill(
    client: OllamaClient,
    question: str,
    index_html: str,
    current_feature_styles: str,
    issue_notes: str = "",
) -> str:
    system_prompt = (
        f"Today: {_today()}. Fill styles.css feature-styles slot only.\n"
        "Rules: use only var(--neu-*) colors and shadows.\n"
        "No raw hex colors, no named colors.\n"
        "Output plain CSS only."
    )
    user_prompt = (
        f"Request: {question}\n\n"
        f"HTML excerpt:\n{_trim(index_html, 2200)}\n\n"
        f"Current feature-styles slot:\n{_trim(current_feature_styles, 1400) or '(empty)'}\n\n"
        f"Issues to fix:\n{_trim(issue_notes, 1000) or '(none)'}"
    )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.18, num_ctx=12288, timeout=300)
    css = re.sub(r"^```(?:css)?\n|```$", "", str(raw or "").strip(), flags=re.MULTILINE).strip()
    return css or current_feature_styles


def _step_readme_slot_fill(
    client: OllamaClient,
    question: str,
    spec: AppSpec,
    feature_list_slot: str,
    run_notes_slot: str,
    research_knowledge: str,
) -> tuple[str, str]:
    system_prompt = (
        f"Today: {_today()}. Fill README canon slots.\n"
        "Return JSON only with keys: feature_list, run_notes.\n"
        "feature_list should be markdown bullets.\n"
        "run_notes should be concise markdown bullets."
    )
    user_prompt = (
        f"Request: {question}\n\n"
        f"Spec:\n{spec_to_json(spec)}\n\n"
        f"Research context:\n{_trim(research_knowledge, 1200) or '(none)'}\n\n"
        f"Current feature-list slot:\n{_trim(feature_list_slot, 1000)}\n\n"
        f"Current run-notes slot:\n{_trim(run_notes_slot, 1000)}"
    )
    raw = _chat(client, system_prompt, user_prompt, temperature=0.25, num_ctx=12288, timeout=240)
    parsed = _parse_json_object(raw)
    feature_list = str(parsed.get("feature_list", "")).strip() or feature_list_slot
    run_notes = str(parsed.get("run_notes", "")).strip() or run_notes_slot
    return feature_list, run_notes


def _step_legacy_migration(
    client: OllamaClient,
    app_dir: Path,
    existing: dict[str, str],
    question: str,
) -> str:
    notes: list[str] = []
    legacy_schema = str(existing.get("schema.sql", "")).strip()
    tables = "\n\n".join(re.findall(r"CREATE TABLE[\s\S]*?;", legacy_schema, re.IGNORECASE))
    seeds = "\n\n".join(re.findall(r"INSERT INTO[\s\S]*?;", legacy_schema, re.IGNORECASE))
    if tables:
        write_slot(app_dir / "schema.sql", "tables", tables)
        notes.append("Ported CREATE TABLE statements from legacy schema.")
    if seeds:
        write_slot(app_dir / "schema.sql", "seeds", seeds)
        notes.append("Ported legacy seed INSERT statements.")

    migration_prompt = (
        "Migrate legacy app content into Canon slot JSON.\n"
        "Return JSON keys: imports_feature, routes_feature, state, methods, computed, on_mounted, "
        "view_feature, head_feature, feature_styles.\n"
        "Adapt Flask routes to envelope helpers ok_item/ok_items/err."
    )
    migration_input = (
        f"User request: {question}\n\n"
        f"Legacy app.py:\n{_trim(existing.get('app.py', ''), 4500)}\n\n"
        f"Legacy index.html:\n{_trim(existing.get('templates/index.html', ''), 2600)}\n\n"
        f"Legacy app.js:\n{_trim(existing.get('static/app.js', ''), 3800)}\n\n"
        f"Legacy styles.css:\n{_trim(existing.get('static/styles.css', ''), 2600)}"
    )
    parsed = _parse_json_object(_chat(client, migration_prompt, migration_input, temperature=0.15, num_ctx=32768, timeout=600))
    if parsed:
        write_slot(app_dir / "app.py", "imports-feature", str(parsed.get("imports_feature", "")).strip())
        write_slot(app_dir / "app.py", "routes-feature", str(parsed.get("routes_feature", "")).strip())
        write_slot(app_dir / "static/app.js", "state", str(parsed.get("state", "")).strip())
        write_slot(app_dir / "static/app.js", "methods", str(parsed.get("methods", "")).strip())
        write_slot(app_dir / "static/app.js", "computed", str(parsed.get("computed", "")).strip())
        write_slot(app_dir / "static/app.js", "on-mounted", str(parsed.get("on_mounted", "")).strip())
        write_slot(app_dir / "templates/index.html", "view-feature", str(parsed.get("view_feature", "")).strip())
        write_slot(app_dir / "templates/index.html", "head-feature", str(parsed.get("head_feature", "")).strip())
        write_slot(app_dir / "static/styles.css", "feature-styles", str(parsed.get("feature_styles", "")).strip())
        notes.append("Mapped legacy Flask/Vue/CSS content into canon slots.")
    else:
        notes.append("Legacy auto-port was partial; fallback slots left for fresh generation.")
    return "\n".join(f"- {line}" for line in notes)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_app_pool(
    question: str,
    repo_root: Path,
    project_slug: str,
    bus: Any,
    research_context: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run Canon v1 app generation pipeline with scaffold + slot-fill architecture."""

    def _prog(stage: str, detail: dict[str, Any] | None = None) -> None:
        if callable(progress_callback):
            try:
                progress_callback(stage, detail or {})
            except Exception:
                pass

    def _cancelled() -> bool:
        if callable(cancel_checker):
            try:
                return bool(cancel_checker())
            except Exception:
                return False
        return False

    bus.emit("app_pool", "start", {"question": question, "project": project_slug})
    client = OllamaClient()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    orchestrator_cfg = lane_model_config(repo_root, "orchestrator_reasoning")
    learning = FeedbackLearningEngine(repo_root, client=client, model_cfg=orchestrator_cfg)
    learned_guidance = learning.guidance_for_lane("make_app", limit=5)
    research_knowledge = "\n\n".join(filter(None, [learned_guidance, _trim(research_context, 3000)]))

    existing = _find_existing_app(repo_root, project_slug)
    is_extend = bool(existing)
    migration_notes = ""

    app_dir = repo_root / "Projects" / project_slug / "implementation" / f"{ts}_app"
    app_dir.mkdir(parents=True, exist_ok=True)
    mode, mode_detail = _step_scaffold_copy(target_dir=app_dir, existing=existing)
    _prog("app_scaffold_copy", {"mode": mode, "detail": mode_detail, "target": str(app_dir)})

    if mode == "migrate_legacy":
        migration_notes = _step_legacy_migration(client, app_dir, existing, question)
        _prog("app_legacy_migration_completed", {"notes": migration_notes})

    if _cancelled():
        return {"ok": False, "message": "Cancelled.", "files": {}}

    slot_files = _slot_paths(app_dir)
    existing_spec_ctx = migration_notes if migration_notes else ""
    spec = _step_spec_generator(client, question, research_knowledge, existing_spec_ctx)
    _prog("app_spec_generated", {"app_name": spec.app_name, "routes": len(spec.routes), "entities": len(spec.entities)})

    current_tables = read_slot(slot_files["schema_sql"], "tables")
    current_seeds = read_slot(slot_files["schema_sql"], "seeds")
    tables_sql, seeds_sql = _step_db_architect_slots(
        client,
        question,
        spec,
        research_knowledge,
        existing_tables=current_tables,
        existing_seeds=current_seeds,
    )
    write_slot(slot_files["schema_sql"], "tables", tables_sql)
    write_slot(slot_files["schema_sql"], "seeds", seeds_sql)
    _prog("app_db_architect_completed", {"tables_lines": tables_sql.count("\n"), "seeds_lines": seeds_sql.count("\n")})

    imports_slot = read_slot(slot_files["app_py"], "imports-feature")
    routes_slot = read_slot(slot_files["app_py"], "routes-feature")
    imports_slot, routes_slot = _step_api_slot_fill(
        client,
        question,
        spec,
        research_knowledge,
        imports_slot,
        routes_slot,
    )
    write_slot(slot_files["app_py"], "imports-feature", imports_slot)
    write_slot(slot_files["app_py"], "routes-feature", routes_slot)
    flask_code = slot_files["app_py"].read_text(encoding="utf-8")
    schema_sql = slot_files["schema_sql"].read_text(encoding="utf-8")
    db_py = slot_files["db_py"].read_text(encoding="utf-8")

    api_validation_error = ""
    for cycle in range(0, 3):
        flask_code = slot_files["app_py"].read_text(encoding="utf-8")
        ok_compile, compile_err = _py_compile_check(flask_code)
        if not ok_compile:
            api_validation_error = f"py_compile failed:\n{compile_err}"
        else:
            ok_smoke, smoke_err = _import_smoke_check(flask_code, db_py, schema_sql)
            if not ok_smoke:
                api_validation_error = f"import smoke check failed:\n{smoke_err}"
            else:
                ok_runtime, runtime_err = _runtime_smoke_check(app_dir, spec)
                if not ok_runtime:
                    api_validation_error = f"runtime smoke check failed:\n{runtime_err}"
                else:
                    api_validation_error = ""
                    break

        if cycle >= 2:
            break
        _prog("app_api_fix_cycle", {"cycle": cycle + 1, "error": api_validation_error[:220]})
        imports_slot, routes_slot = _step_api_slot_fill(
            client,
            question,
            spec,
            research_knowledge,
            read_slot(slot_files["app_py"], "imports-feature"),
            read_slot(slot_files["app_py"], "routes-feature"),
            issue_notes=api_validation_error,
        )
        write_slot(slot_files["app_py"], "imports-feature", imports_slot)
        write_slot(slot_files["app_py"], "routes-feature", routes_slot)

    if api_validation_error:
        _prog("app_api_smoke_warning", {"error": api_validation_error[:220]})

    _present_deps, _missing_deps = _check_dependencies(flask_code)
    if _missing_deps:
        _prog("app_dependencies_warning", {"missing": _missing_deps, "install_hint": "pip install " + " ".join(_missing_deps)})

    vue_plan = _step_vue_architect_spec(client, question, spec, research_knowledge)
    _prog("app_vue_architect_completed", {"preview": vue_plan[:180]})

    current_slots = {
        "state": read_slot(slot_files["app_js"], "state"),
        "methods": read_slot(slot_files["app_js"], "methods"),
        "computed": read_slot(slot_files["app_js"], "computed"),
        "on_mounted": read_slot(slot_files["app_js"], "on-mounted"),
        "view_feature": read_slot(slot_files["index_html"], "view-feature"),
        "head_feature": read_slot(slot_files["index_html"], "head-feature"),
    }
    vue_slots = _step_vue_slot_fill(client, question, spec, vue_plan, research_knowledge, current_slots)
    write_slot(slot_files["app_js"], "state", vue_slots["state"])
    write_slot(slot_files["app_js"], "methods", vue_slots["methods"])
    write_slot(slot_files["app_js"], "computed", vue_slots["computed"])
    write_slot(slot_files["app_js"], "on-mounted", vue_slots["on_mounted"])
    write_slot(slot_files["index_html"], "view-feature", vue_slots["view_feature"])
    write_slot(slot_files["index_html"], "head-feature", vue_slots["head_feature"])

    app_js = slot_files["app_js"].read_text(encoding="utf-8")
    index_html = slot_files["index_html"].read_text(encoding="utf-8")
    flask_code = slot_files["app_py"].read_text(encoding="utf-8")
    schema_sql = slot_files["schema_sql"].read_text(encoding="utf-8")

    html_issues = _check_html_structure(index_html)
    vue_binding_issues = _check_vue_bindings(index_html, app_js)
    if html_issues:
        _prog("app_html_issues", {"issues": html_issues[:8], "count": len(html_issues)})
    if vue_binding_issues:
        _prog("app_vue_binding_issues", {"issues": vue_binding_issues[:8], "count": len(vue_binding_issues)})

    integration_notes = _step_integration_check(client, question, flask_code, app_js, index_html, research_knowledge)
    feature_issues = _check_feature_coverage(client, question, schema_sql, flask_code, index_html, app_js)
    if feature_issues:
        appended = "Feature coverage issues:\n" + "\n".join(f"- {issue}" for issue in feature_issues)
        integration_notes = appended if "integration looks clean" in integration_notes.lower() else f"{integration_notes}\n\n{appended}"

    if "integration looks clean" not in integration_notes.lower():
        imports_slot, routes_slot = _step_api_slot_fill(
            client,
            question,
            spec,
            research_knowledge,
            read_slot(slot_files["app_py"], "imports-feature"),
            read_slot(slot_files["app_py"], "routes-feature"),
            issue_notes=integration_notes,
        )
        write_slot(slot_files["app_py"], "imports-feature", imports_slot)
        write_slot(slot_files["app_py"], "routes-feature", routes_slot)
        vue_slots = _step_vue_slot_fill(
            client,
            question,
            spec,
            vue_plan,
            research_knowledge,
            {
                "state": read_slot(slot_files["app_js"], "state"),
                "methods": read_slot(slot_files["app_js"], "methods"),
                "computed": read_slot(slot_files["app_js"], "computed"),
                "on_mounted": read_slot(slot_files["app_js"], "on-mounted"),
                "view_feature": read_slot(slot_files["index_html"], "view-feature"),
                "head_feature": read_slot(slot_files["index_html"], "head-feature"),
            },
            issue_notes=integration_notes,
        )
        write_slot(slot_files["app_js"], "state", vue_slots["state"])
        write_slot(slot_files["app_js"], "methods", vue_slots["methods"])
        write_slot(slot_files["app_js"], "computed", vue_slots["computed"])
        write_slot(slot_files["app_js"], "on-mounted", vue_slots["on_mounted"])
        write_slot(slot_files["index_html"], "view-feature", vue_slots["view_feature"])
        write_slot(slot_files["index_html"], "head-feature", vue_slots["head_feature"])

    feature_styles = read_slot(slot_files["styles_css"], "feature-styles")
    feature_styles = _step_css_slot_fill(client, question, slot_files["index_html"].read_text(encoding="utf-8"), feature_styles)
    write_slot(slot_files["styles_css"], "feature-styles", feature_styles)

    feature_list_slot = read_slot(slot_files["readme_md"], "feature-list")
    run_notes_slot = read_slot(slot_files["readme_md"], "run-notes")
    feature_list_slot, run_notes_slot = _step_readme_slot_fill(
        client,
        question,
        spec,
        feature_list_slot,
        run_notes_slot,
        research_knowledge,
    )
    write_slot(slot_files["readme_md"], "feature-list", feature_list_slot)
    write_slot(slot_files["readme_md"], "run-notes", run_notes_slot)

    app_py_text = slot_files["app_py"].read_text(encoding="utf-8")
    app_js_text = slot_files["app_js"].read_text(encoding="utf-8")
    feature_styles = read_slot(slot_files["styles_css"], "feature-styles")
    lint_violations = run_policy_lints(
        app_py=app_py_text,
        app_js=app_js_text,
        feature_styles=feature_styles,
        spec=spec,
    )

    if lint_violations:
        lint_blob = "\n".join(
            f"- [{row.get('file')}:{row.get('line')}] {row.get('rule')}: {row.get('message')}"
            for row in lint_violations[:30]
        )
        imports_slot, routes_slot = _step_api_slot_fill(
            client,
            question,
            spec,
            research_knowledge,
            read_slot(slot_files["app_py"], "imports-feature"),
            read_slot(slot_files["app_py"], "routes-feature"),
            issue_notes=lint_blob,
        )
        write_slot(slot_files["app_py"], "imports-feature", imports_slot)
        write_slot(slot_files["app_py"], "routes-feature", routes_slot)
        feature_styles = _step_css_slot_fill(
            client,
            question,
            slot_files["index_html"].read_text(encoding="utf-8"),
            read_slot(slot_files["styles_css"], "feature-styles"),
            issue_notes=lint_blob,
        )
        write_slot(slot_files["styles_css"], "feature-styles", feature_styles)
        app_py_text = slot_files["app_py"].read_text(encoding="utf-8")
        app_js_text = slot_files["app_js"].read_text(encoding="utf-8")
        lint_violations = run_policy_lints(
            app_py=app_py_text,
            app_js=app_js_text,
            feature_styles=read_slot(slot_files["styles_css"], "feature-styles"),
            spec=spec,
        )

    plumbing_divergence = verify_plumbing_intact(app_dir, _CANON_VERSION)
    if plumbing_divergence:
        note = "\n".join(f"- {rel}" for rel in plumbing_divergence)
        integration_notes = (
            f"{integration_notes}\n\nPlumbing divergence detected:\n{note}"
            if integration_notes
            else f"Plumbing divergence detected:\n{note}"
        )

    files_written: dict[str, str] = {}
    for rel in (
        ".canon-version",
        "schema.sql",
        "db.py",
        "app.py",
        "templates/index.html",
        "static/app.js",
        "static/styles.css",
        "README.md",
    ):
        path = app_dir / rel
        if path.exists():
            files_written[rel] = str(path)

    if integration_notes and "integration looks clean" not in integration_notes.lower():
        notes_path = app_dir / "INTEGRATION_NOTES.md"
        notes_path.write_text(f"# Integration Review\n\n{integration_notes}\n", encoding="utf-8")
        files_written["INTEGRATION_NOTES.md"] = str(notes_path)

    if migration_notes.strip():
        migration_path = app_dir / "MIGRATION_NOTES.md"
        migration_path.write_text(f"# Legacy Migration Notes\n\n{migration_notes}\n", encoding="utf-8")
        files_written["MIGRATION_NOTES.md"] = str(migration_path)

    if lint_violations:
        lint_blob = "\n".join(
            f"- [{row.get('file')}:{row.get('line')}] {row.get('rule')}: {row.get('message')}"
            for row in lint_violations
        )
        lint_path = app_dir / "INTEGRATION_NOTES.md"
        prior = lint_path.read_text(encoding="utf-8").strip() if lint_path.exists() else "# Integration Review"
        lint_path.write_text(f"{prior}\n\n## Policy Lints\n{lint_blob}\n", encoding="utf-8")
        files_written["INTEGRATION_NOTES.md"] = str(lint_path)

    mode_line = f"Mode: EXTEND — source build: `{existing.get('__source_dir__', '')}`" if is_extend else "Mode: NEW BUILD"
    summary_md = (
        f"# App Build: {question[:80]}\n\n"
        f"Generated: {ts} | {mode_line} | Canon: `{_CANON_VERSION}`\n\n"
        f"## Files\n"
        + "\n".join(f"- `{rel}`" for rel in sorted(files_written))
        + f"\n\n## App Spec\n\n```json\n{spec_to_json(spec)}\n```\n\n"
        + f"## Integration Review\n\n{integration_notes or 'Integration looks clean.'}\n"
    )
    summary_path = app_dir / "BUILD_SUMMARY.md"
    summary_path.write_text(summary_md, encoding="utf-8")
    files_written["BUILD_SUMMARY.md"] = str(summary_path)

    bus.emit("app_pool", "completed", {"project": project_slug, "path": str(app_dir), "files": sorted(files_written.keys())})
    _prog("app_pool_completed", {"path": str(app_dir), "files": sorted(files_written.keys())})

    return {
        "ok": True,
        "message": f"App built: {len(files_written)} files in {app_dir.name}/",
        "path": str(app_dir),
        "files": files_written,
        "integration_notes": integration_notes,
    }
