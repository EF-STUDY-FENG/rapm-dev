"""Compatibility shim for legacy imports.

Deprecated: import RavenTask and build_items_from_pattern from raven_task.
"""
from raven_task import RavenTask, build_items_from_pattern  # re-export for backward compatibility

__all__ = [
    "RavenTask",
    "build_items_from_pattern",
]
