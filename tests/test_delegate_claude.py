#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "delegate_claude.py"


SEND_SH = r'''#!/usr/bin/env bash
set -euo pipefail
db="${FAKE_AGMSG_DB:?}"
id=1
[ ! -f "$db" ] || id=$(( $(wc -l < "$db") + 1 ))
printf '%s\x1f%s\x1f%s\x1f%s\n' "$id" "$2" "$3" "$4" >> "$db"
echo "Sent to $3 in team $1"
'''


LIST_IDS_SH = r'''#!/usr/bin/env bash
set -euo pipefail
db="${FAKE_AGMSG_DB:?}"
to="$2"
since=0
[ "${3:-}" != "--since-id" ] || since="${4:-0}"
[ -f "$db" ] || exit 0
while IFS=$'\x1f' read -r id from dest body; do
  [ "$id" -gt "$since" ] || continue
  [ "$dest" = "$to" ] || continue
  printf '%s\x1f%s\x1f%s\n' "$id" "$from" "$body"
done < "$db"
'''


WHOAMI_SH = r'''#!/usr/bin/env bash
echo "agent=codex teams=test-team type=codex project=$1"
'''


FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys, time
time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "0")))
model = "fable"
if "--model" in sys.argv:
    model = sys.argv[sys.argv.index("--model") + 1]
size = int(os.environ.get("FAKE_CLAUDE_RESULT_SIZE", "0"))
result = "fake-result" if size <= 0 else "x" * size
print(json.dumps({
  "type": "result",
  "result": result,
  "total_cost_usd": 0.01,
  "modelUsage": {f"claude-{model}-test": {}}
}))
'''


class DelegateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.agmsg = self.base / "agmsg"
        scripts = self.agmsg / "scripts"
        scripts.mkdir(parents=True)
        for name, body in {
            "send.sh": SEND_SH,
            "list-ids.sh": LIST_IDS_SH,
            "whoami.sh": WHOAMI_SH,
        }.items():
            path = scripts / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        self.claude = self.base / "claude"
        self.claude.write_text(FAKE_CLAUDE, encoding="utf-8")
        self.claude.chmod(0o755)
        self.db = self.base / "messages.db.txt"
        self.state = self.base / "state"
        self.env = os.environ.copy()
        self.env["FAKE_AGMSG_DB"] = str(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def command(self, *extra: str) -> list[str]:
        return [
            sys.executable,
            str(SCRIPT),
            "run",
            "--model",
            "fable",
            "--task",
            "Review this bounded proposal.",
            "--team",
            "test-team",
            "--from-agent",
            "codex",
            "--to-agent",
            "claude",
            "--agmsg-dir",
            str(self.agmsg),
            "--state-dir",
            str(self.state),
            "--claude-bin",
            str(self.claude),
            *extra,
        ]

    def run_json(self, command: list[str], env: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(command, text=True, capture_output=True, env=env or self.env, timeout=10)
        return result, json.loads(result.stdout)

    def test_dry_run_has_no_side_effects_and_no_tools(self) -> None:
        result, payload = self.run_json(self.command("--dry-run"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "dry_run")
        self.assertEqual(payload["claude_policy"], {"safe_mode": True, "tools": []})
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_completed_round_trip_reports_actual_model(self) -> None:
        result, payload = self.run_json(self.command("--timeout", "5"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["actual_model"], "claude-fable-test")
        self.assertEqual(payload["result"], "fake-result")
        messages = self.db.read_text(encoding="utf-8")
        self.assertIn("delegate_request", messages)
        self.assertIn("delegate_response", messages)
        self.assertIn(payload["job_id"], messages)

    def test_timeout_returns_running_then_collects(self) -> None:
        env = self.env.copy()
        env["FAKE_CLAUDE_SLEEP"] = "0.5"
        result, payload = self.run_json(self.command("--timeout", "0.05"), env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "running")
        collect = [
            sys.executable,
            str(SCRIPT),
            "collect",
            "--job-id",
            payload["job_id"],
            "--wait",
            "3",
            "--state-dir",
            str(self.state),
        ]
        collected_result, collected = self.run_json(collect, env)
        self.assertEqual(collected_result.returncode, 0, collected_result.stderr)
        self.assertEqual(collected["status"], "completed")
        self.assertEqual(collected["result"], "fake-result")

    def test_large_result_spills_to_job_file(self) -> None:
        env = self.env.copy()
        env["FAKE_CLAUDE_RESULT_SIZE"] = "500"
        result, payload = self.run_json(self.command("--timeout", "5", "--max-message-chars", "100"), env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "completed")
        result_file = Path(payload["result_file"])
        self.assertTrue(result_file.is_file())
        self.assertEqual(len(result_file.read_text(encoding="utf-8")), 500)
        self.assertNotIn('"result":"' + ("x" * 200), self.db.read_text(encoding="utf-8"))

    def test_secret_like_task_is_rejected_before_send(self) -> None:
        command = self.command()
        command[command.index("--task") + 1] = "api_key=super-secret-value"
        result, payload = self.run_json(command)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["status"], "error")
        self.assertIn("redact", payload["error"])
        self.assertFalse(self.db.exists())

    def test_unsafe_route_identifier_is_rejected_before_send(self) -> None:
        command = self.command()
        command[command.index("--team") + 1] = "bad'team"
        result, payload = self.run_json(command)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["status"], "error")
        self.assertIn("team", payload["error"])
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
