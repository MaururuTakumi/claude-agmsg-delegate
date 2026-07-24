#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
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
printf '%s\x1f%s\x1f%s\x1f%s\x1f%s\n' "$id" "$1" "$2" "$3" "$4" >> "$db"
echo "Sent to $3 in team $1"
'''


API_SH = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
if len(args) < 4 or args[:2] != ["get", "teams"] or args[3] != "messages":
    raise SystemExit("unsupported fake api.sh request")
team = args[2]
agent = args[args.index("--agent") + 1] if "--agent" in args else ""
limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 30
db = Path(os.environ["FAKE_AGMSG_DB"])
records = []
if db.is_file():
    for line in db.read_text(encoding="utf-8").splitlines():
        message_id, message_team, from_agent, to_agent, body = line.split("\x1f", 4)
        if message_team != team:
            continue
        if agent and agent not in (from_agent, to_agent):
            continue
        records.append({
            "type": "message_sent",
            "id": message_id,
            "team": message_team,
            "from": from_agent,
            "to": to_agent,
            "body": body,
            "at": "2026-01-01T00:00:00Z",
        })
for record in records[-limit:]:
    print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
'''


LIST_IDS_SH = r'''#!/usr/bin/env bash
set -euo pipefail
db="${FAKE_AGMSG_DB:?}"
team="$1"
to="$2"
since=0
[ "${3:-}" != "--since-id" ] || since="${4:-0}"
[ -f "$db" ] || exit 0
while IFS=$'\x1f' read -r id message_team from dest body; do
  [ "$id" -gt "$since" ] || continue
  [ "$message_team" = "$team" ] || continue
  [ "$dest" = "$to" ] || continue
  if [ "${FAKE_AGMSG_CARET_SEPARATOR:-0}" = "1" ]; then
    printf '%s^_%s^_%s\n' "$id" "$from" "$body"
  else
    printf '%s\x1f%s\x1f%s\n' "$id" "$from" "$body"
  fi
done < "$db"
'''


WHOAMI_SH = r'''#!/usr/bin/env bash
echo "agent=codex teams=test-team type=codex project=$1"
'''


FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
environment_log = os.environ.get("FAKE_CLAUDE_ENV_LOG")
if environment_log:
    with open(environment_log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({
          "future_provider_present": "CLAUDE_CODE_FUTURE_PROVIDER_TOKEN" in os.environ,
          "anthropic_api_key_present": "ANTHROPIC_API_KEY" in os.environ,
        }) + "\n")
if "auth" in args and "status" in args:
    call_number = 1
    counter_path = os.environ.get("FAKE_CLAUDE_AUTH_COUNTER")
    if counter_path:
        try:
            call_number = int(open(counter_path, encoding="utf-8").read()) + 1
        except (FileNotFoundError, ValueError):
            call_number = 1
        with open(counter_path, "w", encoding="utf-8") as handle:
            handle.write(str(call_number))

    auth_method = os.environ.get("FAKE_CLAUDE_AUTH_METHOD", "claude.ai")
    api_provider = os.environ.get("FAKE_CLAUDE_API_PROVIDER", "firstParty")
    subscription_type = os.environ.get("FAKE_CLAUDE_SUBSCRIPTION_TYPE", "max")
    switch_after = int(os.environ.get("FAKE_CLAUDE_AUTH_SWITCH_AFTER", "0"))
    if switch_after and call_number > switch_after:
        auth_method = "api_key"
        subscription_type = ""
    print(json.dumps({
      "loggedIn": os.environ.get("FAKE_CLAUDE_LOGGED_IN", "1") != "0",
      "authMethod": auth_method,
      "apiProvider": api_provider,
      "subscriptionType": subscription_type,
    }))
    raise SystemExit(0)

edit_file = os.environ.get("FAKE_CLAUDE_EDIT_FILE")
enabled_tools = ""
if "--tools" in args:
    enabled_tools = args[args.index("--tools") + 1]
if edit_file and ("Edit" in enabled_tools or "Write" in enabled_tools):
    Path(edit_file).write_text(
        os.environ.get("FAKE_CLAUDE_EDIT_CONTENT", "edited-by-fake-sonnet"),
        encoding="utf-8",
    )

invocation_log = os.environ.get("FAKE_CLAUDE_INVOCATION_LOG")
if invocation_log:
    with open(invocation_log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(args) + "\n")
time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "0")))
model = "fable"
if "--model" in args:
    model = args[args.index("--model") + 1]
size = int(os.environ.get("FAKE_CLAUDE_RESULT_SIZE", "0"))
result = "fake-result" if size <= 0 else "x" * size
print(json.dumps({"type": "system", "subtype": "init"}))
if os.environ.get("FAKE_CLAUDE_SKIP_READ", "0") != "1":
    configured_read = os.environ.get("FAKE_CLAUDE_READ_FILE")
    if configured_read:
        read_file = Path(configured_read)
    elif (Path.cwd() / "target.txt").is_file():
        read_file = Path.cwd() / "target.txt"
    else:
        read_file = Path.cwd() / "README.md"
    print(json.dumps({
      "type": "assistant",
      "message": {
        "role": "assistant",
        "content": [{
          "type": "tool_use",
          "id": "toolu_fake_read",
          "name": "Read",
          "input": {"file_path": str(read_file)},
        }],
      },
    }))
    print(json.dumps({
      "type": "user",
      "message": {
        "role": "user",
        "content": [{
          "type": "tool_result",
          "tool_use_id": "toolu_fake_read",
          "content": "fixture contents",
          "is_error": os.environ.get("FAKE_CLAUDE_READ_ERROR", "0") == "1",
        }],
      },
    }))
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
            "api.sh": API_SH,
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
        blocked_exact = {
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_CUSTOM_HEADERS",
            "AWS_BEARER_TOKEN_BEDROCK",
            "CLAUDE_CODE_API_KEY_HELPER_TTL_MS",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
            "CLAUDE_CODE_SKIP_FOUNDRY_AUTH",
            "CLAUDE_CODE_SKIP_MANTLE_AUTH",
            "CLAUDE_CODE_SKIP_VERTEX_AUTH",
            "CLAUDE_CODE_USE_ANTHROPIC_AWS",
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_FOUNDRY",
            "CLAUDE_CODE_USE_MANTLE",
            "CLAUDE_CODE_USE_VERTEX",
        }
        for name in list(self.env):
            if name in blocked_exact or (
                name.startswith("ANTHROPIC_")
                and (
                    name.endswith("_API_KEY")
                    or name.endswith("_AUTH_TOKEN")
                    or name.endswith("_BASE_URL")
                )
            ):
                self.env.pop(name)
        self.env["FAKE_AGMSG_DB"] = str(self.db)
        self.env["CLAUDE_AGMSG_DELEGATE_TESTING"] = "1"

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

    def doctor_command(self, codex_home: Path | None = None) -> list[str]:
        selected_home = codex_home or self.base / "codex-home"
        skill = selected_home / "skills" / "claude-agmsg-delegate"
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            "---\nname: claude-agmsg-delegate\ndescription: test fixture\n---\n",
            encoding="utf-8",
        )
        (skill / "VERSION").write_text((ROOT / "VERSION").read_text(), encoding="utf-8")
        return [
            sys.executable,
            str(SCRIPT),
            "doctor",
            "--project",
            str(ROOT),
            "--agmsg-dir",
            str(self.agmsg),
            "--state-dir",
            str(self.state),
            "--codex-home",
            str(selected_home),
            "--claude-bin",
            str(self.claude),
        ]

    def test_version_matches_distribution_marker(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--version"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), (ROOT / "VERSION").read_text().strip())

    def test_documented_versions_match_distribution_marker(self) -> None:
        expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        for name in ("README.md", "README.ja.md", "AGENTS.md", "SKILL.md", "llms.txt"):
            contents = (ROOT / name).read_text(encoding="utf-8")
            versions = set(re.findall(r"\b0\.\d+\.\d+\b", contents))
            self.assertEqual(versions, {expected}, f"stale documented version in {name}")

    def test_dry_run_checks_subscription_without_model_or_agmsg_side_effects(self) -> None:
        invocation_log = self.base / "invocations.jsonl"
        env = self.env.copy()
        env["FAKE_CLAUDE_INVOCATION_LOG"] = str(invocation_log)
        result, payload = self.run_json(self.command("--dry-run"), env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "dry_run")
        self.assertEqual(payload["delegate_version"], "0.3.1")
        self.assertEqual(payload["contract_version"], 2)
        self.assertEqual(payload["agmsg_reader"], "api.sh")
        self.assertEqual(
            payload["claude_policy"],
            {
                "safe_mode": True,
                "execution_mode": "workspace_read",
                "tools": ["Read", "Glob", "Grep"],
                "permission_mode": "plan",
                "review_required": False,
                "workspace_grounding_required": True,
                "subscription_only": True,
                "auth_method": "claude.ai",
                "api_provider": "firstParty",
                "subscription_type": "max",
            },
        )
        self.assertEqual(payload["request"]["billing_mode"], "subscription")
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())
        self.assertFalse(invocation_log.exists())

    def test_doctor_reports_healthy_setup_without_mutation(self) -> None:
        result, payload = self.run_json(self.doctor_command())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["delegate_version"], "0.3.1")
        self.assertEqual(payload["contract_version"], 2)
        self.assertFalse(payload["mutating"])
        self.assertFalse(payload["model_invoked"])
        self.assertFalse(payload["network_required"])
        self.assertEqual(payload["issues"], [])
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_doctor_identifies_uninstalled_skill_outdated_agmsg_and_off_path_claude(self) -> None:
        (self.agmsg / "scripts" / "api.sh").unlink()
        (self.agmsg / "VERSION").write_text("1.1.7\n", encoding="utf-8")
        fake_home = self.base / "fresh-home"
        local_bin = fake_home / ".local" / "bin"
        local_bin.mkdir(parents=True)
        discovered_claude = local_bin / "claude"
        discovered_claude.write_text(FAKE_CLAUDE, encoding="utf-8")
        discovered_claude.chmod(0o755)
        codex_home = fake_home / ".codex"
        command = self.doctor_command(codex_home)
        skill = codex_home / "skills" / "claude-agmsg-delegate"
        for child in skill.iterdir():
            child.unlink()
        skill.rmdir()
        command[command.index("--claude-bin"):command.index("--claude-bin") + 2] = []
        env = self.env.copy()
        env["HOME"] = str(fake_home)
        env["PATH"] = "/usr/bin:/bin"
        result, payload = self.run_json(command, env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(payload["status"], "issues")
        codes = {item["code"] for item in payload["issues"]}
        self.assertIn("SKILL_NOT_INSTALLED", codes)
        self.assertIn("AGMSG_OUTDATED", codes)
        self.assertIn("CLAUDE_BIN_OUTSIDE_PATH", codes)
        claude_check = next(item for item in payload["checks"] if item["name"] == "claude_binary")
        self.assertEqual(claude_check["path"], str(discovered_claude.resolve()))
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_doctor_accepts_legacy_reader_with_warning(self) -> None:
        scripts = self.agmsg / "scripts"
        (scripts / "api.sh").unlink()
        legacy = scripts / "list-ids.sh"
        legacy.write_text(LIST_IDS_SH, encoding="utf-8")
        legacy.chmod(0o755)
        result, payload = self.run_json(self.doctor_command())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "ok")
        issues = {item["code"]: item for item in payload["issues"]}
        self.assertEqual(issues["AGMSG_LEGACY_READER"]["severity"], "warning")
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_doctor_reports_alternate_agmsg_without_switching(self) -> None:
        fake_home = self.base / "alternate-home"
        alternate_scripts = fake_home / ".agents" / "skills" / "agmsg" / "scripts"
        alternate_scripts.mkdir(parents=True)
        for name, body in {"send.sh": SEND_SH, "api.sh": API_SH, "whoami.sh": WHOAMI_SH}.items():
            path = alternate_scripts / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        selected = self.base / "missing-agmsg"
        command = self.doctor_command()
        command[command.index("--agmsg-dir") + 1] = str(selected)
        env = self.env.copy()
        env["HOME"] = str(fake_home)
        result, payload = self.run_json(command, env)
        self.assertEqual(result.returncode, 1, result.stderr)
        issues = {item["code"]: item for item in payload["issues"]}
        self.assertIn("AGMSG_NOT_INSTALLED", issues)
        self.assertIn("AGMSG_ALTERNATE_INSTALL_FOUND", issues)
        self.assertEqual(
            issues["AGMSG_ALTERNATE_INSTALL_FOUND"]["evidence"]["alternates"],
            [str(alternate_scripts.parent.resolve())],
        )
        selected_check = next(item for item in payload["checks"] if item["name"] == "agmsg")
        self.assertEqual(selected_check["path"], str(selected))
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_run_discovers_claude_outside_path_and_pins_absolute_path(self) -> None:
        fake_home = self.base / "discovery-home"
        local_bin = fake_home / ".local" / "bin"
        local_bin.mkdir(parents=True)
        discovered_claude = local_bin / "claude"
        discovered_claude.write_text(FAKE_CLAUDE, encoding="utf-8")
        discovered_claude.chmod(0o755)
        command = self.command("--dry-run")
        index = command.index("--claude-bin")
        del command[index:index + 2]
        env = self.env.copy()
        env["HOME"] = str(fake_home)
        env["PATH"] = "/usr/bin:/bin"
        result, payload = self.run_json(command, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["claude_bin"], str(discovered_claude.resolve()))
        self.assertTrue(payload["claude_outside_path"])
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_inferred_route_uses_headless_delegate_mailboxes(self) -> None:
        command = self.command("--dry-run")
        for option in ["--team", "--from-agent", "--to-agent"]:
            index = command.index(option)
            del command[index:index + 2]
        result, payload = self.run_json(command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["team"], "test-team")
        self.assertEqual(payload["from_agent"], "codex-delegate")
        self.assertEqual(payload["to_agent"], "claude-delegate")
        self.assertFalse(self.db.exists())

    def test_completed_round_trip_reports_actual_model(self) -> None:
        invocation_log = self.base / "invocations.jsonl"
        env = self.env.copy()
        env["FAKE_CLAUDE_INVOCATION_LOG"] = str(invocation_log)
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["delegate_version"], "0.3.1")
        self.assertEqual(payload["contract_version"], 2)
        self.assertTrue(payload["workspace_grounded"])
        self.assertEqual(payload["files_read"], ["README.md"])
        self.assertEqual(payload["actual_model"], "claude-fable-test")
        self.assertEqual(payload["result"], "fake-result")
        self.assertEqual(payload["billing_mode"], "subscription")
        self.assertEqual(payload["auth_method"], "claude.ai")
        self.assertEqual(payload["api_provider"], "firstParty")
        self.assertEqual(payload["subscription_type"], "max")
        self.assertEqual(payload["execution_mode"], "workspace_read")
        self.assertEqual(payload["tools"], ["Read", "Glob", "Grep"])
        self.assertEqual(payload["permission_mode"], "plan")
        self.assertFalse(payload["review_required"])
        self.assertNotIn("cost_usd", payload)
        self.assertNotIn("total_cost_usd", payload)
        public_output = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("total_cost_usd", public_output)
        self.assertNotIn('"cost_usd"', public_output)
        invocation = json.loads(invocation_log.read_text(encoding="utf-8").splitlines()[0])
        self.assertIn("MUST use Read", invocation[0])
        self.assertIn("project-relative paths", invocation[0])
        self.assertIn("-p", invocation)
        self.assertIn("--no-session-persistence", invocation)
        self.assertIn("--verbose", invocation)
        output_index = invocation.index("--output-format")
        self.assertEqual(invocation[output_index + 1], "stream-json")
        self.assertNotIn("--max-budget-usd", invocation)
        setting_sources_index = invocation.index("--setting-sources")
        self.assertEqual(invocation[setting_sources_index + 1], "")
        tools_index = invocation.index("--tools")
        self.assertEqual(invocation[tools_index + 1], "Read,Glob,Grep")
        permission_index = invocation.index("--permission-mode")
        self.assertEqual(invocation[permission_index + 1], "plan")
        self.assertNotIn("Edit", invocation[tools_index + 1])
        self.assertNotIn("Write", invocation[tools_index + 1])
        self.assertNotIn("Bash", invocation[tools_index + 1])
        messages = self.db.read_text(encoding="utf-8")
        self.assertIn("delegate_request", messages)
        self.assertIn("delegate_response", messages)
        self.assertIn(payload["job_id"], messages)
        self.assertNotIn("total_cost_usd", messages)
        self.assertNotIn('"cost_usd"', messages)
        saved_state = next(self.state.glob("*/state.json")).read_text(encoding="utf-8")
        self.assertNotIn("total_cost_usd", saved_state)
        self.assertNotIn('"cost_usd"', saved_state)

    def test_fable_reads_project_directory_without_editing(self) -> None:
        project = self.base / "read-project"
        project.mkdir()
        target = project / "target.txt"
        target.write_text("must-stay-unchanged", encoding="utf-8")

        command = self.command("--timeout", "5", "--project", str(project))
        invocation_log = self.base / "read-invocations.jsonl"
        env = self.env.copy()
        env["FAKE_CLAUDE_INVOCATION_LOG"] = str(invocation_log)
        env["FAKE_CLAUDE_EDIT_FILE"] = str(target)

        result, payload = self.run_json(command, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "must-stay-unchanged")
        self.assertEqual(payload["execution_mode"], "workspace_read")
        self.assertEqual(payload["tools"], ["Read", "Glob", "Grep"])
        self.assertEqual(payload["permission_mode"], "plan")
        self.assertFalse(payload["review_required"])
        self.assertTrue(payload["workspace_grounded"])
        self.assertEqual(payload["files_read"], ["target.txt"])

        invocation = json.loads(invocation_log.read_text(encoding="utf-8").splitlines()[0])
        tools_index = invocation.index("--tools")
        self.assertEqual(invocation[tools_index + 1], "Read,Glob,Grep")
        permission_index = invocation.index("--permission-mode")
        self.assertEqual(invocation[permission_index + 1], "plan")
        self.assertNotIn("Edit", invocation[tools_index + 1])
        self.assertNotIn("Write", invocation[tools_index + 1])
        self.assertNotIn("Bash", invocation[tools_index + 1])

    def test_fable_implementer_role_remains_read_only_without_workspace_write(self) -> None:
        command = self.command("--role", "implementer", "--timeout", "5")
        result, payload = self.run_json(command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["role"], "implementer")
        self.assertEqual(payload["execution_mode"], "workspace_read")
        self.assertEqual(payload["tools"], ["Read", "Glob", "Grep"])
        self.assertEqual(payload["permission_mode"], "plan")
        self.assertFalse(payload["review_required"])

    def test_sonnet_workspace_write_edits_git_workspace_and_requires_review(self) -> None:
        project = self.base / "write-project"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        target = project / "target.txt"
        target.write_text("before", encoding="utf-8")

        command = self.command("--workspace-write", "--timeout", "5")
        command[command.index("--model") + 1] = "sonnet"
        command.extend(["--role", "implementer", "--project", str(project)])
        invocation_log = self.base / "workspace-invocations.jsonl"
        env = self.env.copy()
        env["FAKE_CLAUDE_INVOCATION_LOG"] = str(invocation_log)
        env["FAKE_CLAUDE_EDIT_FILE"] = str(target)

        result, payload = self.run_json(command, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "edited-by-fake-sonnet")
        self.assertEqual(payload["execution_mode"], "workspace_write")
        self.assertEqual(payload["tools"], ["Read", "Edit", "Write", "Glob", "Grep"])
        self.assertEqual(payload["permission_mode"], "acceptEdits")
        self.assertTrue(payload["review_required"])
        self.assertTrue(payload["workspace_grounded"])
        self.assertEqual(payload["files_read"], ["target.txt"])

        invocation = json.loads(invocation_log.read_text(encoding="utf-8").splitlines()[0])
        tools_index = invocation.index("--tools")
        self.assertEqual(invocation[tools_index + 1], "Read,Edit,Write,Glob,Grep")
        permission_index = invocation.index("--permission-mode")
        self.assertEqual(invocation[permission_index + 1], "acceptEdits")
        self.assertNotIn("Bash", invocation[tools_index + 1])
        self.assertNotIn("--dangerously-skip-permissions", invocation)

    def test_workspace_write_rejects_non_sonnet_or_non_git_project_before_send(self) -> None:
        result, payload = self.run_json(
            self.command("--role", "implementer", "--workspace-write", "--dry-run")
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --model sonnet", payload["error"])
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

        non_git = self.base / "not-git"
        non_git.mkdir()
        command = self.command("--workspace-write", "--dry-run")
        command[command.index("--model") + 1] = "sonnet"
        command.extend(["--role", "implementer", "--project", str(non_git)])
        result, payload = self.run_json(command)
        self.assertEqual(result.returncode, 2)
        self.assertIn("command failed: git", payload["error"])
        self.assertFalse(self.db.exists())

    def test_official_agmsg_api_round_trip_does_not_require_list_ids(self) -> None:
        self.assertFalse((self.agmsg / "scripts" / "list-ids.sh").exists())
        result, payload = self.run_json(self.command("--timeout", "5"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["result"], "fake-result")
        saved = json.loads(next(self.state.glob("*/state.json")).read_text(encoding="utf-8"))
        self.assertEqual(saved["agmsg_reader"], "api.sh")
        self.assertIsInstance(saved["request_message_id"], str)
        self.assertIsInstance(saved["response_message_id"], str)

    def test_legacy_list_ids_caret_separator_remains_compatible(self) -> None:
        scripts = self.agmsg / "scripts"
        (scripts / "api.sh").unlink()
        list_ids = scripts / "list-ids.sh"
        list_ids.write_text(LIST_IDS_SH, encoding="utf-8")
        list_ids.chmod(0o755)
        env = self.env.copy()
        env["FAKE_AGMSG_CARET_SEPARATOR"] = "1"
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["billing_mode"], "subscription")
        self.assertEqual(payload["result"], "fake-result")

    def test_missing_official_message_reader_stops_with_update_guidance(self) -> None:
        (self.agmsg / "scripts" / "api.sh").unlink()
        result, payload = self.run_json(self.command("--dry-run"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["status"], "error")
        self.assertIn("install or update official agmsg", payload["error"])
        self.assertIn("api.sh", payload["error"])
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_timeout_returns_running_then_collects(self) -> None:
        env = self.env.copy()
        env["FAKE_CLAUDE_SLEEP"] = "0.5"
        result, payload = self.run_json(self.command("--timeout", "0.05"), env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["worker_stage"], "claude_inference")
        self.assertGreaterEqual(payload["running_seconds"], 0)
        self.assertIn("--wait 60", payload["collect_command"])
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

    def test_result_is_discarded_without_observed_project_read(self) -> None:
        env = self.env.copy()
        env["FAKE_CLAUDE_SKIP_READ"] = "1"
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("no successful Read tool call", payload["error"])
        self.assertNotIn("result", payload)

    def test_result_is_discarded_when_read_tool_fails(self) -> None:
        env = self.env.copy()
        env["FAKE_CLAUDE_READ_ERROR"] = "1"
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("no successful Read tool call", payload["error"])
        self.assertNotIn("result", payload)

    def test_result_is_discarded_when_read_leaves_project(self) -> None:
        outside = self.base / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        env = self.env.copy()
        env["FAKE_CLAUDE_READ_FILE"] = str(outside)
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("outside the selected project", payload["error"])
        self.assertNotIn("result", payload)

    def test_collect_marks_dead_running_worker_failed_immediately(self) -> None:
        job_id = "cad-dead-worker"
        directory = self.state / job_id
        directory.mkdir(parents=True)
        state = {
            "job_id": job_id,
            "status": "running",
            "delegate_version": "0.3.1",
            "contract_version": 2,
            "model": "fable",
            "role": "reviewer",
            "execution_mode": "workspace_read",
            "tools": ["Read", "Glob", "Grep"],
            "permission_mode": "plan",
            "review_required": False,
            "billing_mode": "subscription",
            "worker_pid": 99999999,
            "worker_stage": "claude_inference",
            "created_at": "2026-01-01T00:00:00+00:00",
            "created_epoch": time.time(),
            "updated_at": "2026-01-01T00:00:00+00:00",
            "ttl_seconds": 3600,
        }
        (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
        collect = [
            sys.executable,
            str(SCRIPT),
            "collect",
            "--job-id",
            job_id,
            "--wait",
            "0",
            "--state-dir",
            str(self.state),
        ]
        result, payload = self.run_json(collect)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["worker_stage"], "worker_exited")
        self.assertIn("worker exited", payload["error"])

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

    def test_api_and_cloud_provider_environment_is_rejected_before_send(self) -> None:
        for name in [
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX",
            "CLAUDE_CODE_USE_FOUNDRY",
            "CLAUDE_CODE_OAUTH_TOKEN",
        ]:
            with self.subTest(name=name):
                env = self.env.copy()
                env[name] = "test-only-value"
                result, payload = self.run_json(self.command("--dry-run"), env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(payload["status"], "error")
                self.assertIn("subscription-only policy", payload["error"])
                self.assertIn(name, payload["error"])
                self.assertFalse(self.db.exists())
                self.assertFalse(self.state.exists())

    def test_unknown_future_provider_environment_is_not_passed_to_claude(self) -> None:
        env = self.env.copy()
        environment_log = self.base / "claude-environment.jsonl"
        env["CLAUDE_CODE_FUTURE_PROVIDER_TOKEN"] = "test-only-value"
        env["FAKE_CLAUDE_ENV_LOG"] = str(environment_log)
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "completed")
        entries = [json.loads(line) for line in environment_log.read_text().splitlines()]
        self.assertGreaterEqual(len(entries), 4)
        self.assertTrue(all(not entry["future_provider_present"] for entry in entries))
        self.assertTrue(all(not entry["anthropic_api_key_present"] for entry in entries))

    def test_non_subscription_auth_status_is_rejected_before_send(self) -> None:
        env = self.env.copy()
        env["FAKE_CLAUDE_AUTH_METHOD"] = "api_key"
        env["FAKE_CLAUDE_SUBSCRIPTION_TYPE"] = ""
        result, payload = self.run_json(self.command("--dry-run"), env)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["status"], "error")
        self.assertIn("authMethod=claude.ai", payload["error"])
        self.assertFalse(self.db.exists())
        self.assertFalse(self.state.exists())

    def test_logged_out_status_is_rejected_before_send(self) -> None:
        env = self.env.copy()
        env["FAKE_CLAUDE_LOGGED_IN"] = "0"
        result, payload = self.run_json(self.command("--dry-run"), env)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["status"], "error")
        self.assertIn("loggedIn=true", payload["error"])
        self.assertFalse(self.db.exists())

    def test_worker_rechecks_auth_and_does_not_infer_after_auth_changes(self) -> None:
        env = self.env.copy()
        auth_counter = self.base / "auth-counter.txt"
        invocation_log = self.base / "invocations.jsonl"
        env["FAKE_CLAUDE_AUTH_COUNTER"] = str(auth_counter)
        env["FAKE_CLAUDE_AUTH_SWITCH_AFTER"] = "1"
        env["FAKE_CLAUDE_INVOCATION_LOG"] = str(invocation_log)
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["billing_mode"], "subscription_required")
        self.assertIn("subscription-only policy", payload["error"])
        self.assertEqual(auth_counter.read_text(encoding="utf-8"), "2")
        self.assertFalse(invocation_log.exists())
        messages = self.db.read_text(encoding="utf-8")
        self.assertIn("delegate_request", messages)
        self.assertIn("delegate_response", messages)

    def test_postflight_auth_change_discards_inference_result(self) -> None:
        env = self.env.copy()
        auth_counter = self.base / "auth-counter.txt"
        invocation_log = self.base / "invocations.jsonl"
        env["FAKE_CLAUDE_AUTH_COUNTER"] = str(auth_counter)
        env["FAKE_CLAUDE_AUTH_SWITCH_AFTER"] = "2"
        env["FAKE_CLAUDE_INVOCATION_LOG"] = str(invocation_log)
        result, payload = self.run_json(self.command("--timeout", "5"), env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["billing_mode"], "subscription")
        self.assertEqual(payload["auth_method"], "claude.ai")
        self.assertEqual(payload["api_provider"], "firstParty")
        self.assertIn("subscription-only policy", payload["error"])
        self.assertNotIn("result", payload)
        self.assertEqual(auth_counter.read_text(encoding="utf-8"), "3")
        self.assertTrue(invocation_log.exists())


if __name__ == "__main__":
    unittest.main()
