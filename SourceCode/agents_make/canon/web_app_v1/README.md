# Generated Web App

This project uses the Oathweaver Canon v1 stack:
- Flask 3.x backend
- Vue 3.5 (CDN, no build step) frontend
- SQLite (`sqlite3`) persistence

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install flask flask-cors
python app.py
```

Open `http://127.0.0.1:5000`.

## Files

- `app.py` - Flask routes and envelope helpers
- `db.py` - SQLite connection lifecycle helpers
- `schema.sql` - schema and optional seed data
- `templates/index.html` - Vue mount shell
- `static/app.js` - Vue app logic
- `static/styles.css` - canonical neuromorphic base + feature styles

## Features

<!-- region: feature-list -->
- No feature details added yet.
<!-- endregion: feature-list -->

## Run Notes

<!-- region: run-notes -->
- Health check endpoint: `GET /api/health`
<!-- endregion: run-notes -->
