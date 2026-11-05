# vulnclaw-plugin-demo

Working example of a third-party VulnClaw detection plugin. It is a real
plugin, not a stub: it flags `Set-Cookie` values missing `Secure`, `HttpOnly`
or `SameSite`.

## Install

```bash
pip install ./examples/plugins/vulnclaw-plugin-demo
```

The package declares one entry point in the `vulnclaw.plugins` group, which is
the same mechanism `vulnclaw plugins list --external` and the Web UI plugin
inventory use to discover third-party plugins.

## Run

```bash
vulnclaw plugins info demo.web.cookie_flags
vulnclaw plugins run demo.web.cookie_flags \
  --target https://example.com \
  --input cookies.json
```

`cookies.json`:

```json
{"set_cookie": ["sid=abc; Path=/", "csrf=xyz; Path=/; Secure; HttpOnly"]}
```

Expected: one finding for `sid`, none for `csrf`.

## Plugin contract

- `plugin_id` — globally unique, dotted id. Required.
- `stages` — where the kernel may call the plugin.
- `permissions` — subset of `network`, `filesystem`, `subprocess`. The registry
  rejects anything else at registration time.
- `min_core_version` — refuse to load on older cores.
- `run(context)` — returns a `PluginResult`; raise nothing, report through
  `PluginResult.error_result` / `skipped_result` so one plugin cannot abort a run.
