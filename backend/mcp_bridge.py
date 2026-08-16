#!/usr/bin/env python3
"""
BidVex MCP stdio bridge — iter485/iter486.

Claude Desktop speaks the MCP protocol over **stdio** (JSON-RPC 2.0
messages, newline-delimited, on stdin/stdout). This script is what
Claude Desktop launches as a subprocess to talk to the BidVex MCP
server, which is exposed over HTTP JSON-RPC at
`{BIDVEX_MCP_URL}/api/mcp/rpc`.

Role
----
* Read newline-delimited JSON-RPC requests from stdin.
* Forward each to the HTTP endpoint with a Bearer token.
* Write the response (or nothing, for notifications) as a single
  newline-terminated JSON line to stdout.

Environment variables
---------------------
BIDVEX_MCP_URL         (required) — Base URL, e.g. https://your-bidvex.example.com
BIDVEX_MCP_JWT         (required) — The user's BidVex JWT (obtain via /api/auth/login)
BIDVEX_MCP_TIMEOUT     (optional) — Per-request timeout seconds (default 60)

Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS, `%APPDATA%\\Claude\\claude_desktop_config.json` on Windows):

    {
      "mcpServers": {
        "bidvex": {
          "command": "python",
          "args":    ["/absolute/path/to/backend/mcp_bridge.py"],
          "env": {
            "BIDVEX_MCP_URL": "https://your-bidvex.example.com",
            "BIDVEX_MCP_JWT": "eyJhbGciOi..."
          }
        }
      }
    }

The bridge is intentionally tiny and stateless: every stdin line is
forwarded, every HTTP response is written back. No caching, no
transformation, so the entire MCP-compliance surface lives in
`backend/mcp_server.py`.

Exit codes
----------
0 — clean EOF on stdin (Claude Desktop closed the connection)
1 — fatal configuration error (missing env vars)
2 — fatal transport error (unrecoverable HTTP failure). Claude Desktop
    will restart the subprocess.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

import httpx

# NOTE: log to stderr — stdout is reserved for JSON-RPC responses.
def _log(msg: str) -> None:
    print(f"[bidvex-bridge] {msg}", file=sys.stderr, flush=True)


def _load_env() -> tuple[str, str, float]:
    url = os.environ.get("BIDVEX_MCP_URL")
    jwt = os.environ.get("BIDVEX_MCP_JWT")
    timeout = float(os.environ.get("BIDVEX_MCP_TIMEOUT") or "60")
    if not url:
        _log("FATAL: BIDVEX_MCP_URL not set")
        sys.exit(1)
    if not jwt:
        _log("FATAL: BIDVEX_MCP_JWT not set")
        sys.exit(1)
    return url.rstrip("/"), jwt, timeout


async def _forward_one(client: httpx.AsyncClient, url: str, msg: Dict[str, Any]) -> Optional[Any]:
    """Forward one JSON-RPC message to the HTTP endpoint. Returns the
    parsed response object, or None on notifications (server returned
    202)."""
    try:
        r = await client.post(url, json=msg)
    except httpx.HTTPError as exc:
        _log(f"HTTP error forwarding {msg.get('method')}: {type(exc).__name__}: {exc}")
        # Return a JSON-RPC error to the client so Claude Desktop can see it.
        return {"jsonrpc": "2.0", "id": msg.get("id"), "error": {
            "code":    -32603,
            "message": "bridge_upstream_unreachable",
            "data":    {"type": type(exc).__name__},
        }}
    if r.status_code == 202:
        return None
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"jsonrpc": "2.0", "id": msg.get("id"), "error": {
            "code":    -32603,
            "message": "bridge_bad_upstream_response",
            "data":    {"status_code": r.status_code, "text": r.text[:200]},
        }}


async def _run() -> int:
    base_url, jwt, timeout = _load_env()
    rpc_url = f"{base_url}/api/mcp/rpc"
    headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}

    _log(f"starting stdio bridge → {rpc_url}")

    # Read from stdin in a background task; write to stdout synchronously.
    loop = asyncio.get_running_loop()
    stdin_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stdin_reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        while True:
            line = await stdin_reader.readline()
            if not line:
                _log("stdin EOF — shutting down")
                return 0
            line_text = line.decode("utf-8", errors="replace").strip()
            if not line_text:
                continue
            try:
                msg = json.loads(line_text)
            except json.JSONDecodeError as exc:
                _log(f"invalid JSON line dropped: {exc}")
                continue

            # Batch or single
            if isinstance(msg, list):
                responses = []
                for one in msg:
                    if not isinstance(one, dict):
                        continue
                    r = await _forward_one(client, rpc_url, one)
                    if r is not None:
                        responses.append(r)
                if responses:
                    sys.stdout.write(json.dumps(responses) + "\n")
                    sys.stdout.flush()
            elif isinstance(msg, dict):
                r = await _forward_one(client, rpc_url, msg)
                if r is not None:
                    sys.stdout.write(json.dumps(r) + "\n")
                    sys.stdout.flush()


def main() -> None:
    try:
        code = asyncio.run(_run())
    except KeyboardInterrupt:
        code = 0
    except Exception as exc:  # noqa: BLE001
        _log(f"fatal: {type(exc).__name__}: {exc}")
        code = 2
    sys.exit(code)


if __name__ == "__main__":
    main()
