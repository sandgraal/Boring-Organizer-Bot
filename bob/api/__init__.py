"""B.O.B API server module.

Provides a local-only HTTP API for the web interface.
"""

from bob.api.app import create_app

__all__ = ["create_app"]
