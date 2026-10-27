"""AI Director: reads each wave's telemetry and decides how enemies evolve.

Use `Director` (director/director.py). It asks Claude when an API key is
available and falls back to the deterministic rules in director/rules.py.
"""
from director.director import Decision, Director

__all__ = ["Decision", "Director"]
