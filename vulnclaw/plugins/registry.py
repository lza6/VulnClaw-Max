from __future__ import annotations

import re
from typing import TypeVar

from vulnclaw.plugins.base import VulnPlugin
from vulnclaw.plugins.result import PluginStage

ALLOWED_PERMISSIONS = frozenset({"network", "filesystem", "subprocess"})

PluginType = TypeVar("PluginType", bound=type[VulnPlugin])


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, type[VulnPlugin]] = {}

    @staticmethod
    def _validate_plugin(plugin_cls: type[VulnPlugin]) -> None:
        permissions = set(getattr(plugin_cls, "permissions", ()) or ())
        unknown = permissions - ALLOWED_PERMISSIONS
        if unknown:
            raise ValueError(f"Plugin {plugin_cls.plugin_id} requests unknown permissions: {sorted(unknown)}")
        min_version = str(getattr(plugin_cls, "min_core_version", "") or "")
        if min_version:
            from vulnclaw import __version__

            def parts(value: str) -> tuple[int, ...]:
                return tuple(int(item) for item in re.findall(r"\d+", value)[:3])

            if parts(__version__) < parts(min_version):
                raise ValueError(
                    f"Plugin {plugin_cls.plugin_id} requires core >= {min_version}, got {__version__}"
                )

    def register(self, plugin_cls: PluginType, *, replace: bool = False) -> PluginType:
        plugin_id = getattr(plugin_cls, "plugin_id", "")
        if not plugin_id:
            raise ValueError("Plugin class must define plugin_id")
        self._validate_plugin(plugin_cls)
        if plugin_id in self._plugins and not replace:
            raise ValueError(f"Plugin already registered: {plugin_id}")
        self._plugins[plugin_id] = plugin_cls
        return plugin_cls

    def unregister(self, plugin_id: str) -> None:
        self._plugins.pop(plugin_id, None)

    def clear(self) -> None:
        self._plugins.clear()

    def get(self, plugin_id: str) -> type[VulnPlugin] | None:
        return self._plugins.get(plugin_id)

    def require(self, plugin_id: str) -> type[VulnPlugin]:
        plugin_cls = self.get(plugin_id)
        if plugin_cls is None:
            raise KeyError(f"Plugin not found: {plugin_id}")
        return plugin_cls

    def list(self) -> list[type[VulnPlugin]]:
        return list(self._plugins.values())

    def names(self) -> list[str]:
        return sorted(self._plugins)

    def load_entry_points(
        self,
        group: str = "vulnclaw.plugins",
        *,
        errors: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        """Load third-party plugins declared through package entry points.

        When ``errors`` is supplied, a broken entry point is recorded there and
        the remaining plugins still load — that is what an inventory listing
        needs. Without it the first failure raises, which is what CLI callers
        want: silently skipping a broken plugin during a scan would hide a
        misconfiguration.
        """
        from importlib.metadata import entry_points

        try:
            selected = entry_points(group=group)
        except TypeError:  # Python 3.10 selectable API fallback
            selected = entry_points().get(group, [])  # type: ignore[union-attr]

        loaded: list[dict[str, object]] = []
        for entry in selected:
            try:
                plugin_cls = entry.load()
                if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, VulnPlugin)):
                    raise TypeError(f"Entry point {entry.name!r} did not resolve to a VulnPlugin")
                self.register(plugin_cls, replace=True)
            except Exception as exc:
                if errors is None:
                    raise
                errors.append({"entry_point": entry.name, "error": str(exc)})
                continue
            loaded.append(plugin_cls.metadata())
        return loaded

    def metadata(self) -> list[dict[str, object]]:
        return [plugin_cls.metadata() for plugin_cls in self._plugins.values()]

    def by_stage(self, stage: PluginStage | str) -> list[type[VulnPlugin]]:
        stage_value = PluginStage(stage) if isinstance(stage, str) else stage
        return [plugin_cls for plugin_cls in self._plugins.values() if stage_value in plugin_cls.stages]

    def by_tag(self, tag: str) -> list[type[VulnPlugin]]:
        return [plugin_cls for plugin_cls in self._plugins.values() if tag in plugin_cls.tags]

    @property
    def count(self) -> int:
        return len(self._plugins)


registry = PluginRegistry()
