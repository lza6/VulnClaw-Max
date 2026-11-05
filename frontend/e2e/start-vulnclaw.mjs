import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..");
const configDir = process.env.VULNCLAW_E2E_CONFIG || path.join(root, ".test-tmp", "e2e-config");

rmSync(configDir, { recursive: true, force: true });
mkdirSync(configDir, { recursive: true });
writeFileSync(
  path.join(configDir, "config.yaml"),
  [
    "llm:",
    "  provider: custom",
    "  base_url: http://127.0.0.1:19090/v1",
    "  model: mock",
    "  api_key: test-key",
    "session:",
    "  language: en",
    "",
  ].join("\n"),
  "utf-8",
);

const child = spawn(
  process.env.PYTHON || "python",
  ["-m", "vulnclaw", "web", "--host", "127.0.0.1", "--port", "8877"],
  {
    cwd: root,
    env: {
      ...process.env,
      VULNCLAW_CONFIG_DIR: configDir,
      PYTHONIOENCODING: "utf-8",
    },
    stdio: "inherit",
  },
);

function shutdown() {
  child.kill();
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
child.on("exit", (code) => process.exit(code ?? 0));
