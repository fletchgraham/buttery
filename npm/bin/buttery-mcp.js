#!/usr/bin/env node
// Launches the buttery MCP server (Python) on stdio.
// Prefers `uvx buttery mcp` (no install needed); falls back to an installed `buttery` CLI.
"use strict";
const { spawnSync, spawn } = require("node:child_process");

function has(cmd) {
  const r = spawnSync(cmd, ["--version"], { stdio: "ignore" });
  return !r.error && r.status === 0;
}

const extra = process.argv.slice(2);
let cmd, args;
if (has("uvx")) {
  cmd = "uvx";
  args = ["buttery", "mcp", ...extra];
} else if (has("buttery")) {
  cmd = "buttery";
  args = ["mcp", ...extra];
} else {
  process.stderr.write(
    "buttery-mcp: needs Python 3.11+ and either `uv` (https://docs.astral.sh/uv/) " +
      "or the buttery package (`pip install buttery`).\n",
  );
  process.exit(1);
}

const child = spawn(cmd, args, { stdio: "inherit" });
child.on("error", (err) => {
  process.stderr.write(`buttery-mcp: failed to start ${cmd}: ${err.message}\n`);
  process.exit(1);
});
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
