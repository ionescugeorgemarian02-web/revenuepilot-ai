"""Run the local-only health endpoint: python -m revenuepilot."""

from .app import serve


if __name__ == "__main__":
    serve()
