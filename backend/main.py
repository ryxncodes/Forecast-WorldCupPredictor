"""Vercel FastAPI entrypoint.

The local app lives at app.main:app. Vercel's FastAPI runtime looks for an
`app` object at common entrypoint files, so this tiny shim keeps local imports
unchanged while making the backend service easy to detect.
"""

from app.main import app
