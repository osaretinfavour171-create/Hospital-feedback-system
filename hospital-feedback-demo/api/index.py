"""Vercel serverless entrypoint for the HFD FastAPI backend.

Vercel's Python runtime detects the ASGI ``app`` object in this module and
serves it. Requests to ``/api/*`` are rewritten here (see vercel.json).
"""
import os
import sys

# Make the backend package importable regardless of the runtime's cwd.
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from main import app  # noqa: E402
