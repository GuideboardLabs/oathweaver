"""Canonical Flask web-app scaffold with slot regions for feature code."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from db import close_db, get_db, init_db, row_to_dict

# region: imports-feature
# endregion: imports-feature

BASE_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "static"),
    template_folder=str(BASE_DIR / "templates"),
)
CORS(app)
app.config["JSON_SORT_KEYS"] = False


@app.teardown_appcontext
def _teardown_db(error: BaseException | None = None) -> None:
    """Close the request database connection."""
    close_db(error)


with app.app_context():
    init_db()


def ok_item(payload: dict[str, Any], status: int = 200):
    """Return a single-item success envelope."""
    return jsonify({"item": payload}), status


def ok_items(payloads: list[dict[str, Any]], status: int = 200):
    """Return a collection success envelope."""
    return jsonify({"items": payloads, "meta": {"count": len(payloads)}}), status


def err(code: str, message: str, status: int = 400, details: Any = None):
    """Return a canonical error envelope."""
    return jsonify({"error": {"code": str(code), "message": str(message), "details": details}}), status


@app.errorhandler(400)
def _bad_request(error: BaseException):
    """Handle bad request errors."""
    return err("BAD_REQUEST", str(error), status=400)


@app.errorhandler(404)
def _not_found(_error: BaseException):
    """Handle not found errors."""
    return err("NOT_FOUND", "Resource not found", status=404)


@app.errorhandler(405)
def _method_not_allowed(_error: BaseException):
    """Handle method-not-allowed errors."""
    return err("METHOD_NOT_ALLOWED", "Method not allowed", status=405)


@app.errorhandler(500)
def _server_error(error: BaseException):
    """Handle uncaught server errors."""
    return err("INTERNAL_ERROR", "Internal server error", status=500)


@app.get("/")
def index():
    """Serve the Vue application shell."""
    return render_template("index.html")


@app.get("/api/health")
def health():
    """Return a basic health payload."""
    return ok_item({"status": "ok"})


# region: routes-feature
# endregion: routes-feature


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "").strip() == "1",
        port=int(os.environ.get("PORT", "5000")),
    )
