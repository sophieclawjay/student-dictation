"""Deterministic subprocess protocol fixture, with no inference or microphone."""

import json
import sys
import time

request = json.loads(sys.stdin.readline())
mode = request.get("mode", "success")
print(json.dumps({"type": "status", "message": "Fixture started"}), flush=True)
if mode == "sleep":
    time.sleep(30)
elif mode == "error":
    print(json.dumps({"type": "error", "message": "Fixture failure"}), flush=True)
    raise SystemExit(1)
elif mode == "invalid":
    print("invalid response", flush=True)
elif mode == "crash":
    raise SystemExit(3)
else:
    print(
        json.dumps(
            {"type": "result", "kind": "transcription", "text": "New words.", "language": "en"}
        ),
        flush=True,
    )
