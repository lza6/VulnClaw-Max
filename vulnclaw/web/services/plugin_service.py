"""Plugin inventory for the Web UI.

The registry is process-global and starts with the builtin plugins; this service
adds the third-party entry-point plugins on demand and reports load failures
per entry point so a single broken package cannot blank the whole list.
"""

from __future__ import annotations

import logging

from vulnclaw.plugins import register_builtin_plugins, registry
from vulnclaw.plugins.web import BUILTIN_WEB_PLUGINS

logger = logging.getLogger(__name__)

_BUILTIN_IDS = frozenset(plugin_cls.plugin_id for plugin_cls in BUILTIN_WEB_PLUGINS)


def list_plugins(*, include_external: bool = True) -> dict[str, list[dict]]:
    """Return ``{"plugins": [...], "errors": [...]}`` for the inventory view."""
    errors: list[dict] = []
    register_builtin_plugins()
    if include_external:
        try:
            registry.load_entry_points(errors=errors)
        except Exception as exc:  # entry-point discovery itself failed
            logger.warning("External plugin discovery failed: %s", exc)
            errors.append({"entry_point": "discovery", "error": str(exc)})
    plugins: list[dict] = []
    for plugin_cls in registry.list():
        meta = plugin_cls.metadata()
        meta["origin"] = "builtin" if plugin_cls.plugin_id in _BUILTIN_IDS else "external"
        plugins.append(meta)
    plugins.sort(key=lambda item: (str(item.get("origin")), str(item.get("plugin_id"))))
    return {"plugins": plugins, "errors": errors}


def get_plugin(plugin_id: str, *, include_external: bool = True) -> dict | None:
    """Return a single plugin's metadata, or ``None`` when absent."""
    inventory = list_plugins(include_external=include_external)
    for item in inventory["plugins"]:
        if item.get("plugin_id") == plugin_id:
            return item
    return None
