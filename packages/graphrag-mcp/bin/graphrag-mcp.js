#!/usr/bin/env node

/**
 * graphrag-mcp launcher
 *
 * Starts the GraphRAG MCP server by invoking the Python package.
 * Resolution order:
 *   1. uvx graphrag-mcp   (installs from PyPI on first run, fastest for end users)
 *   2. python -m graphrag_mcp  (fallback if uvx is not installed)
 *
 * Environment variables:
 *   GRAPHRAG_ROOT         Path to graphrag project (required unless --root is passed)
 *   GRAPHRAG_DATA         Optional override for index output directory
 *   GRAPHRAG_MCP_CMD      Override the Python launch command entirely
 *                         e.g. GRAPHRAG_MCP_CMD="uv run python -m graphrag_mcp"
 */

"use strict";

const { spawn } = require("child_process");

const args = process.argv.slice(2);

function launch(cmd, cmdArgs) {
  const child = spawn(cmd, cmdArgs, {
    stdio: "inherit",
    env: process.env,
    shell: false,
  });

  child.on("error", (err) => {
    if (err.code === "ENOENT") {
      // Command not found — caller handles fallback
      child.emit("not-found");
    } else {
      process.stderr.write(`graphrag-mcp: ${err.message}\n`);
      process.exit(1);
    }
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
    } else {
      process.exit(code ?? 0);
    }
  });

  return child;
}

function startWithUvx() {
  const child = launch("uvx", ["graphrag-mcp", ...args]);
  child.on("not-found", () => {
    process.stderr.write(
      "graphrag-mcp: uvx not found, falling back to python -m graphrag_mcp\n"
    );
    startWithPython();
  });
}

function startWithPython() {
  // Prefer python3 on Unix, python on Windows
  const python = process.platform === "win32" ? "python" : "python3";
  const child = launch(python, ["-m", "graphrag_mcp", ...args]);
  child.on("not-found", () => {
    process.stderr.write(
      [
        "graphrag-mcp: Could not start the GraphRAG MCP server.",
        "",
        "Install one of the following:",
        "  pip install graphrag-mcp",
        "  uv tool install graphrag-mcp",
        "  pipx install graphrag-mcp",
        "",
      ].join("\n")
    );
    process.exit(1);
  });
}

// Allow complete override via env var
const customCmd = process.env.GRAPHRAG_MCP_CMD;
if (customCmd) {
  const parts = customCmd.split(" ");
  launch(parts[0], [...parts.slice(1), ...args]);
} else {
  startWithUvx();
}
