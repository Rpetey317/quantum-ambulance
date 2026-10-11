"""Private Pitchr AI-judge rehearsal via its documented MCP endpoint.

Session credentials and complete histories stay in a user-selected temporary
directory. Scores are evaluator outputs, not endorsements by the named people.
"""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


ENDPOINT = "https://www.pitchr.studio/api/mcp"


def rpc(endpoint, payload, session=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    request = Request(endpoint, data=json.dumps(payload).encode(), headers=headers)
    with urlopen(request, timeout=55) as response:
        raw = response.read().decode()
        return json.loads(raw) if raw else {}, response.headers.get("Mcp-Session-Id")


def initialize(root):
    """Create the credentials file only in the caller's temporary directory."""
    root.mkdir(parents=True, exist_ok=True)
    payload, session = rpc(ENDPOINT, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "quantum-ambulance-rehearsal", "version": "1.0"},
        },
    })
    if "error" in payload:
        raise RuntimeError(payload["error"])
    rpc(ENDPOINT, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    credentials = {"endpoint": ENDPOINT, "session": session}
    root.joinpath("session.json").write_text(json.dumps(credentials), encoding="utf-8")
    return credentials


def call(root, name, arguments):
    if root.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Keep Pitchr credentials outside the repository; use a temporary directory.")
    session_file = root / "session.json"
    session = (
        json.loads(session_file.read_text(encoding="utf-8"))
        if session_file.exists() else initialize(root)
    )
    arguments = dict(arguments)
    if name == "create_pitch":
        # Private rehearsal is the scope authorized for this utility.
        arguments["visibility"] = "private"
    payload, _ = rpc(session["endpoint"], {
        "jsonrpc": "2.0", "id": 10, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }, session.get("session"))
    if "error" in payload:
        raise RuntimeError(payload["error"])
    result = payload["result"]
    text = "\n".join(part.get("text", "") for part in result.get("content", []))
    if result.get("isError"):
        raise RuntimeError(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--arguments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = call(args.session_dir, args.tool, json.loads(args.arguments.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "status": result.get("status", result.get("pitch", {}).get("status")),
        "url": result.get("url"),
    }, ensure_ascii=True))
