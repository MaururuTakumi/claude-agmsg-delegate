#!/usr/bin/env python3
"""Delegate bounded review or implementation work to Claude through agmsg.

The wrapper owns all agmsg I/O. Advisory jobs may read the current project directory
with a narrow file-tool allowlist but cannot edit files or run commands. Explicit
Sonnet implementation jobs may inspect and edit that worktree and must be reviewed
by Codex. Long calls continue in a detached worker and can be collected later by
job ID. Claude is invoked only when Claude Code proves that the active credential
is a paid Claude.ai subscription; API-key and cloud-provider routes fail closed
before inference.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "expired"}
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,127}$")
ROUTE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
PAID_SUBSCRIPTION_TYPES = {"pro", "max", "team", "enterprise"}
WORKSPACE_READ_TOOLS = ["Read", "Glob", "Grep"]
WORKSPACE_WRITE_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep"]
DELEGATE_VERSION = "0.2.1"
CONTRACT_VERSION = 2
SAFE_CLAUDE_ENV_NAMES = {
    "HOME",
    "LANG",
    "LOGNAME",
    "NO_COLOR",
    "PATH",
    "SHELL",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TEMP",
    "TERM",
    "TMP",
    "TMPDIR",
    "USER",
}
FORBIDDEN_AUTH_ENV_NAMES = {
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


class DelegateError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def now_epoch() -> float:
    return time.time()


def default_state_dir() -> Path:
    return Path.home() / ".cache" / "codex" / "claude-agmsg-delegate" / "jobs"


def default_agmsg_dir() -> Path:
    return Path.home() / ".agents" / "skills" / "agmsg"


def emit(data: dict[str, Any], code: int = 0) -> int:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


def fail(message: str, *, job_id: str | None = None, code: int = 1) -> int:
    payload: dict[str, Any] = {"status": "error", "error": redact(message)}
    if job_id:
        payload["job_id"] = job_id
    return emit(payload, code)


def redact(text: str, limit: int = 1000) -> str:
    output = text
    for pattern in SENSITIVE_PATTERNS:
        output = pattern.sub("<redacted>", output)
    return output if len(output) <= limit else output[:limit] + "..."


def assert_safe_task(task: str, max_chars: int) -> None:
    if not task.strip():
        raise DelegateError("task must not be empty")
    if len(task) > max_chars:
        raise DelegateError(f"task length {len(task)} exceeds max {max_chars}")
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(task):
            raise DelegateError("task appears to contain a secret or credential; summarize and redact it first")


def validate_job_id(job_id: str) -> None:
    if not JOB_ID_RE.fullmatch(job_id):
        raise DelegateError("job_id must be 6-128 characters using letters, digits, dot, underscore, or dash")


def validate_route_id(label: str, value: str) -> None:
    if not ROUTE_ID_RE.fullmatch(value):
        raise DelegateError(
            f"{label} must be 1-64 characters using letters, digits, dot, underscore, or dash"
        )


def require_git_worktree(project: Path) -> Path:
    if not project.is_dir():
        raise DelegateError(f"project directory does not exist: {project}")
    result = run_checked(
        ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
        timeout=15,
    )
    root = Path(result.stdout.strip()).expanduser().resolve()
    try:
        project.relative_to(root)
    except ValueError as exc:
        raise DelegateError("workspace-write project must be inside its Git worktree") from exc
    return root


def execution_policy(workspace_write: bool) -> dict[str, Any]:
    if workspace_write:
        return {
            "execution_mode": "workspace_write",
            "tools": list(WORKSPACE_WRITE_TOOLS),
            "permission_mode": "acceptEdits",
            "review_required": True,
        }
    return {
        "execution_mode": "workspace_read",
        "tools": list(WORKSPACE_READ_TOOLS),
        "permission_mode": "plan",
        "review_required": False,
    }


def make_job_id(model: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"cad-{model}-{stamp}-{secrets.token_hex(3)}"


def scripts_dir(agmsg_dir: Path) -> Path:
    return agmsg_dir.expanduser().resolve() / "scripts"


def required_script(agmsg_dir: Path, name: str) -> Path:
    path = scripts_dir(agmsg_dir) / name
    if not path.is_file() or not os.access(path, os.X_OK):
        raise DelegateError(f"required agmsg script is missing or not executable: {path}")
    return path


def optional_script(agmsg_dir: Path, name: str) -> Path | None:
    path = scripts_dir(agmsg_dir) / name
    if path.is_file() and os.access(path, os.X_OK):
        return path
    return None


def validate_agmsg_transport(agmsg_dir: Path) -> str:
    """Validate the public agmsg transport and return its message reader."""
    required_script(agmsg_dir, "whoami.sh")
    required_script(agmsg_dir, "send.sh")
    if optional_script(agmsg_dir, "api.sh") is not None:
        return "api.sh"
    if optional_script(agmsg_dir, "list-ids.sh") is not None:
        return "list-ids.sh (legacy compatibility)"
    raise DelegateError(
        "agmsg has no supported message reader; install or update official agmsg so "
        f"{scripts_dir(agmsg_dir) / 'api.sh'} exists and is executable"
    )


def run_checked(
    args: list[str],
    *,
    timeout: float = 30,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, env=env, cwd=cwd)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise DelegateError(f"command failed: {Path(args[0]).name}: {redact(detail)}")
    return result


def is_forbidden_auth_env(name: str) -> bool:
    if name in FORBIDDEN_AUTH_ENV_NAMES:
        return True
    return name.startswith("ANTHROPIC_") and (
        name.endswith("_API_KEY")
        or name.endswith("_AUTH_TOKEN")
        or name.endswith("_BASE_URL")
    )


def subscription_env(source: dict[str, str] | None = None) -> dict[str, str]:
    source_env = dict(os.environ if source is None else source)
    blocked = sorted(
        name for name, value in source_env.items() if value and is_forbidden_auth_env(name)
    )
    if blocked:
        raise DelegateError(
            "subscription-only policy blocked credential or provider environment variable(s): "
            + ", ".join(blocked)
            + "; unset them and authenticate with `claude auth login`"
        )
    # Pass only environment variables Claude needs for local execution. This
    # prevents a future, not-yet-known provider selector from silently reaching
    # the CLI. Tests get a narrow FAKE_* passthrough that cannot carry auth keys.
    env = {
        name: value
        for name, value in source_env.items()
        if name in SAFE_CLAUDE_ENV_NAMES or name.startswith("LC_")
    }
    if source_env.get("CLAUDE_AGMSG_DELEGATE_TESTING") == "1":
        env.update(
            (name, value)
            for name, value in source_env.items()
            if name.startswith("FAKE_")
        )

    # These are defense in depth, not substitutes for the auth-status check.
    # DISABLE_EXTRA_USAGE_COMMAND removes the in-CLI enablement surface; an
    # already enabled account-level usage-credit setting must be disabled in
    # Claude Settings > Usage. The README keeps that proof boundary explicit.
    env["DISABLE_EXTRA_USAGE_COMMAND"] = "1"
    env["CLAUDE_CODE_DISABLE_1M_CONTEXT"] = "1"
    return env


def verify_subscription_auth(claude_bin: str, project: Path) -> dict[str, str]:
    env = subscription_env()
    result = run_checked(
        [
            claude_bin,
            "--safe-mode",
            "--setting-sources",
            "",
            "auth",
            "status",
            "--json",
        ],
        timeout=15,
        env=env,
        cwd=project,
    )
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DelegateError(f"Claude auth status returned invalid JSON: {exc}") from exc
    if not isinstance(status, dict):
        raise DelegateError("Claude auth status is not a JSON object")

    logged_in = status.get("loggedIn") is True
    auth_method = str(status.get("authMethod") or "")
    api_provider = str(status.get("apiProvider") or "")
    subscription_type = str(status.get("subscriptionType") or "").lower()
    if not (
        logged_in
        and auth_method == "claude.ai"
        and api_provider == "firstParty"
        and subscription_type in PAID_SUBSCRIPTION_TYPES
    ):
        raise DelegateError(
            "subscription-only policy requires loggedIn=true, authMethod=claude.ai, "
            "apiProvider=firstParty, and a paid subscriptionType; Claude was not invoked"
        )
    return {
        "billing_mode": "subscription",
        "auth_method": auth_method,
        "api_provider": api_provider,
        "subscription_type": subscription_type,
    }


def infer_identity(project: Path, agmsg_dir: Path) -> tuple[str, str]:
    whoami = required_script(agmsg_dir, "whoami.sh")
    output = run_checked([str(whoami), str(project), "codex"]).stdout.strip()
    if "multiple=true" in output or "not_joined=true" in output or "suggest=true" in output:
        raise DelegateError(f"agmsg identity is ambiguous; pass --team and --from-agent explicitly: {output}")
    fields: dict[str, str] = {}
    for item in output.split():
        if "=" in item:
            key, value = item.split("=", 1)
            fields[key] = value
    agent = fields.get("agent", "")
    teams = [team for team in fields.get("teams", "").split(",") if team]
    if not agent or len(teams) != 1:
        raise DelegateError(f"could not infer one agmsg identity/team; pass explicit routing: {output}")
    return teams[0], agent


def send_message(agmsg_dir: Path, team: str, from_agent: str, to_agent: str, body: str) -> None:
    send = required_script(agmsg_dir, "send.sh")
    run_checked([str(send), team, from_agent, to_agent, body])


def list_messages(agmsg_dir: Path, team: str, agent: str, limit: int = 1000) -> list[dict[str, str]]:
    api = optional_script(agmsg_dir, "api.sh")
    if api is not None:
        output = run_checked(
            [
                str(api),
                "get",
                "teams",
                team,
                "messages",
                "--agent",
                agent,
                "--limit",
                str(limit),
            ]
        ).stdout
        messages: list[dict[str, str]] = []
        for line_number, line in enumerate(output.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DelegateError(
                    f"agmsg api.sh returned invalid JSONL on line {line_number}: {exc}"
                ) from exc
            if not isinstance(item, dict) or item.get("type") != "message_sent":
                raise DelegateError(
                    f"agmsg api.sh returned an unexpected messages record on line {line_number}"
                )
            required = ("id", "team", "from", "to", "body")
            if any(not isinstance(item.get(field), str) for field in required):
                raise DelegateError(
                    f"agmsg api.sh returned an invalid messages record on line {line_number}"
                )
            if item["team"] != team:
                continue
            messages.append({field: item[field] for field in required})
        return messages

    # Older private installations may already have the pre-release reader used
    # by this Skill. Keep it as a compatibility path, but never require it from
    # a fresh official agmsg installation.
    list_ids = required_script(agmsg_dir, "list-ids.sh")
    output = run_checked([str(list_ids), team, agent, "--since-id", "0"]).stdout
    messages: list[dict[str, str]] = []
    for line in output.splitlines():
        # sqlite3 3.50+ escapes ASCII control characters in CLI output by
        # default, so char(31) may arrive as the printable two-byte sequence
        # "^_". Older versions and fixtures return the raw unit separator.
        separator = "\x1f" if "\x1f" in line else "^_"
        parts = line.split(separator, 2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        messages.append(
            {"id": parts[0], "team": team, "from": parts[1], "to": agent, "body": parts[2]}
        )
    return messages


def find_job_message(
    messages: list[dict[str, str]],
    job_id: str,
    expected_from: str,
    expected_to: str,
    expected_type: str,
) -> tuple[str, dict[str, Any]]:
    for message in reversed(messages):
        if message["from"] != expected_from or message["to"] != expected_to:
            continue
        try:
            payload = json.loads(message["body"])
        except json.JSONDecodeError:
            continue
        if payload.get("job_id") == job_id and payload.get("type") == expected_type:
            return message["id"], payload
    raise DelegateError(f"agmsg message for job_id={job_id} was not found after send")


def job_dir(state_dir: Path, job_id: str) -> Path:
    validate_job_id(job_id)
    return state_dir.expanduser().resolve() / job_id


def state_path(state_dir: Path, job_id: str) -> Path:
    return job_dir(state_dir, job_id) / "state.json"


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    tmp = path.with_suffix(f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def read_state(state_dir: Path, job_id: str) -> dict[str, Any]:
    path = state_path(state_dir, job_id)
    if not path.is_file():
        raise DelegateError(f"unknown job_id: {job_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DelegateError(f"failed to read job state: {exc}") from exc
    if not isinstance(data, dict):
        raise DelegateError("job state is not a JSON object")
    return data


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    response = state.get("response") if isinstance(state.get("response"), dict) else {}
    raw_status = state.get("status")
    output: dict[str, Any] = {
        "job_id": state.get("job_id"),
        "status": "running" if raw_status in {"queued", "running"} else raw_status,
        "delegate_version": response.get("delegate_version", state.get("delegate_version")),
        "contract_version": response.get("contract_version", state.get("contract_version")),
        "requested_model": state.get("model"),
        "role": state.get("role"),
        "execution_mode": response.get("execution_mode", state.get("execution_mode")),
        "tools": response.get("tools", state.get("tools", [])),
        "permission_mode": response.get("permission_mode", state.get("permission_mode")),
        "review_required": response.get("review_required", state.get("review_required", False)),
        "billing_mode": response.get("billing_mode", state.get("billing_mode")),
        "auth_method": response.get("auth_method", state.get("auth_method")),
        "api_provider": response.get("api_provider", state.get("api_provider")),
        "subscription_type": response.get("subscription_type", state.get("subscription_type")),
        "created_at": state.get("created_at"),
        "updated_at": state.get("updated_at"),
    }
    for key in [
        "actual_model",
        "result",
        "result_preview",
        "result_file",
        "elapsed_seconds",
        "error",
        "workspace_grounded",
        "files_read",
        "worker_stage",
    ]:
        value = response.get(key, state.get(key))
        if value is not None:
            output[key] = value
    if raw_status in {"queued", "running"}:
        output["running_seconds"] = round(
            max(0.0, now_epoch() - float(state.get("created_epoch") or now_epoch())), 3
        )
    output["collect_command"] = (
        f"python3 {Path(__file__).resolve()} collect --job-id {state.get('job_id')} --wait 60"
    )
    return output


def choose_actual_model(model_usage: Any, requested: str) -> str | None:
    if not isinstance(model_usage, dict):
        return None
    keys = [str(key) for key in model_usage]
    for key in keys:
        if requested.lower() in key.lower():
            return key
    non_helper = [key for key in keys if "haiku" not in key.lower()]
    return non_helper[0] if non_helper else (keys[0] if keys else None)


def claude_prompt(state: dict[str, Any]) -> str:
    role = state["role"]
    task = state["request"]["task"]
    if state.get("execution_mode") == "workspace_write":
        return (
            "You are Claude acting as a bounded implementation worker for Codex. "
            "Inspect and edit the current Git workspace now using only the provided file tools. "
            "Before answering, you MUST use Read on at least one relevant existing project file; "
            "do not rely only on the task summary. "
            "Do not run shell commands, install dependencies, deploy, push, access unrelated paths, "
            "or make the final decision. Keep edits scoped to the task. In the final response, list "
            "the files read and changed using project-relative paths, summarize the implementation, "
            "and suggest tests for Codex to run and review.\n\n"
            f"Task retrieved from agmsg job {state['job_id']}:\n{task}"
        )
    return (
        f"You are Claude acting as a bounded advisory {role} for Codex. "
        "Inspect the current project directory using only Read, Glob, and Grep. Before answering, "
        "you MUST use Read on at least one relevant existing project file; do not rely only on the "
        "task summary. "
        "Do not access files outside this project directory or inspect credential, private-key, or environment-secret files. "
        "Do not edit or write files, run commands, deploy, push, install, or make the final decision. "
        "Label assumptions, list the files inspected using project-relative paths, and return the "
        "requested deliverable.\n\n"
        f"Task retrieved from agmsg job {state['job_id']}:\n{task}"
    )


def claude_command(state: dict[str, Any]) -> list[str]:
    command = [
        state["claude_bin"],
        claude_prompt(state),
        "-p",
        "--model",
        state["model"],
        "--effort",
        state["effort"],
        "--safe-mode",
        "--setting-sources",
        "",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--tools",
        ",".join(state.get("tools", [])),
    ]
    if state.get("permission_mode"):
        command.extend(["--permission-mode", state["permission_mode"]])
    return command


def parse_claude_stream(stdout: str, project: Path) -> tuple[dict[str, Any], list[str]]:
    """Parse Claude Code JSONL and return its result plus observed Read evidence."""
    result_event: dict[str, Any] | None = None
    read_calls: dict[str, str] = {}
    failed_tool_ids: set[str] = set()

    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DelegateError(
                f"Claude stream-json returned invalid JSONL on line {line_number}: {exc}"
            ) from exc
        if not isinstance(event, dict):
            raise DelegateError(f"Claude stream-json line {line_number} is not an object")

        if event.get("type") == "result":
            result_event = event

        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "Read":
                tool_id = str(block.get("id") or f"line-{line_number}")
                tool_input = block.get("input")
                if not isinstance(tool_input, dict):
                    continue
                path_value = tool_input.get("file_path") or tool_input.get("path")
                if isinstance(path_value, str) and path_value.strip():
                    read_calls[tool_id] = path_value
            if block.get("type") == "tool_result" and block.get("is_error") is True:
                failed_tool_ids.add(str(block.get("tool_use_id") or ""))

    if result_event is None:
        raise DelegateError("Claude stream-json did not contain a final result event")

    project = project.expanduser().resolve()
    files_read: list[str] = []
    for tool_id, raw_path in read_calls.items():
        if tool_id in failed_tool_ids:
            continue
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = project / candidate
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(project)
        except ValueError as exc:
            raise DelegateError(
                "Claude Read accessed a path outside the selected project; the result was discarded"
            ) from exc
        relative_text = relative.as_posix()
        if relative_text not in files_read:
            files_read.append(relative_text)

    if not files_read:
        raise DelegateError(
            "workspace grounding is required, but no successful Read tool call was observed; "
            "the result was discarded"
        )
    return result_event, files_read


def update_worker_stage(state_dir: Path, state: dict[str, Any], stage: str) -> None:
    state["worker_stage"] = stage
    state["updated_at"] = now_iso()
    write_json_atomic(state_path(state_dir, str(state["job_id"])), state)


def worker_main(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state = read_state(state_dir, args.job_id)
    state["status"] = "running"
    state["worker_pid"] = os.getpid()
    update_worker_stage(state_dir, state, "auth_preflight")
    started = time.monotonic()
    subscription_auth: dict[str, str] | None = None
    try:
        subscription_auth = verify_subscription_auth(
            state["claude_bin"], Path(state["project"])
        )
        update_worker_stage(state_dir, state, "claude_inference")
        command = claude_command(state)
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=float(state["ttl_seconds"]),
            env=subscription_env(),
            cwd=Path(state["project"]),
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise DelegateError(f"Claude failed: {redact(detail)}")
        update_worker_stage(state_dir, state, "auth_postflight")
        postflight_auth = verify_subscription_auth(
            state["claude_bin"], Path(state["project"])
        )
        if postflight_auth != subscription_auth:
            raise DelegateError(
                "subscription-only policy detected an authentication change during inference; "
                "the result was discarded"
            )
        model_output, files_read = parse_claude_stream(
            result.stdout, Path(state["project"])
        )
        text_result = model_output.get("result")
        if not isinstance(text_result, str) or not text_result.strip():
            raise DelegateError("Claude returned an empty result")

        actual_model = choose_actual_model(model_output.get("modelUsage"), state["model"])
        response: dict[str, Any] = {
            "type": "delegate_response",
            "job_id": state["job_id"],
            "status": "completed",
            "delegate_version": state["delegate_version"],
            "contract_version": state["contract_version"],
            "requested_model": state["model"],
            "actual_model": actual_model,
            "role": state["role"],
            "execution_mode": state["execution_mode"],
            "tools": state["tools"],
            "permission_mode": state["permission_mode"],
            "review_required": state["review_required"],
            "billing_mode": subscription_auth["billing_mode"],
            "auth_method": subscription_auth["auth_method"],
            "api_provider": subscription_auth["api_provider"],
            "subscription_type": subscription_auth["subscription_type"],
            "workspace_grounded": True,
            "files_read": files_read,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        if len(text_result) <= int(state["max_message_chars"]):
            response["result"] = text_result
        else:
            result_file = job_dir(state_dir, state["job_id"]) / "result.md"
            result_file.write_text(text_result, encoding="utf-8")
            try:
                result_file.chmod(0o600)
            except OSError:
                pass
            response["result_preview"] = text_result[:500] + "..."
            response["result_file"] = str(result_file)

        update_worker_stage(state_dir, state, "response_correlation")
        send_message(
            Path(state["agmsg_dir"]),
            state["team"],
            state["to_agent"],
            state["from_agent"],
            json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        )
        message_id, verified = find_job_message(
            list_messages(Path(state["agmsg_dir"]), state["team"], state["from_agent"]),
            state["job_id"],
            state["to_agent"],
            state["from_agent"],
            "delegate_response",
        )
        state["status"] = "completed"
        state["worker_stage"] = "completed"
        state["response_message_id"] = message_id
        state["response"] = verified
        state["updated_at"] = now_iso()
        write_json_atomic(state_path(state_dir, state["job_id"]), state)
        return 0
    except subprocess.TimeoutExpired:
        error = f"Claude exceeded worker TTL of {state['ttl_seconds']} seconds"
    except Exception as exc:  # worker must always leave terminal state
        error = redact(str(exc))

    response = {
        "type": "delegate_response",
        "job_id": state["job_id"],
        "status": "failed",
        "delegate_version": state.get("delegate_version", DELEGATE_VERSION),
        "contract_version": state.get("contract_version", CONTRACT_VERSION),
        "requested_model": state["model"],
        "role": state["role"],
        "execution_mode": state["execution_mode"],
        "tools": state["tools"],
        "permission_mode": state["permission_mode"],
        "review_required": state["review_required"],
        "billing_mode": (
            subscription_auth["billing_mode"]
            if subscription_auth is not None
            else "subscription_required"
        ),
        "error": error,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    if subscription_auth is not None:
        response["auth_method"] = subscription_auth["auth_method"]
        response["api_provider"] = subscription_auth["api_provider"]
        response["subscription_type"] = subscription_auth["subscription_type"]
    try:
        send_message(
            Path(state["agmsg_dir"]),
            state["team"],
            state["to_agent"],
            state["from_agent"],
            json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        )
    except Exception as send_exc:
        response["agmsg_error"] = redact(str(send_exc))
    state["status"] = "failed"
    state["worker_stage"] = "failed"
    state["response"] = response
    state["updated_at"] = now_iso()
    write_json_atomic(state_path(state_dir, state["job_id"]), state)
    return 1


def wait_for_state(state_dir: Path, job_id: str, wait_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        state = read_state(state_dir, job_id)
        if state.get("status") in TERMINAL_STATUSES:
            return state
        if time.monotonic() >= deadline:
            return state
        time.sleep(0.2)


def maybe_expire(state_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") in TERMINAL_STATUSES:
        return state
    created = float(state.get("created_epoch") or now_epoch())
    ttl = float(state.get("ttl_seconds") or 3600)
    pid = int(state.get("worker_pid") or 0)
    alive = False
    if pid > 0:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            alive = False
    if state.get("status") == "running" and pid > 0 and not alive:
        state["status"] = "failed"
        state["worker_stage"] = "worker_exited"
        state["error"] = "detached worker exited before writing a terminal result"
        state["updated_at"] = now_iso()
        write_json_atomic(state_path(state_dir, str(state["job_id"])), state)
    elif now_epoch() - created > ttl and not alive:
        state["status"] = "expired"
        state["error"] = "job TTL expired without a live worker"
        state["updated_at"] = now_iso()
        write_json_atomic(state_path(state_dir, str(state["job_id"])), state)
    return state


def run_main(args: argparse.Namespace) -> int:
    model = args.model
    role = args.role or ("reviewer" if model == "fable" else "implementer")
    assert_safe_task(args.task, args.max_task_chars)
    job_id = args.job_id or make_job_id(model)
    validate_job_id(job_id)
    project = Path(args.project).expanduser().resolve()
    agmsg_dir = Path(args.agmsg_dir).expanduser().resolve()
    state_dir = Path(args.state_dir).expanduser().resolve()
    agmsg_reader = validate_agmsg_transport(agmsg_dir)

    if args.timeout < 0:
        raise DelegateError("timeout must be zero or greater")
    if args.ttl <= 0:
        raise DelegateError("ttl must be greater than zero")
    if args.max_task_chars <= 0 or args.max_message_chars <= 0:
        raise DelegateError("max_task_chars and max_message_chars must be greater than zero")
    if not project.is_dir():
        raise DelegateError(f"project directory does not exist: {project}")
    if args.workspace_write and (model != "sonnet" or role != "implementer"):
        raise DelegateError("--workspace-write requires --model sonnet and --role implementer")
    if args.workspace_write:
        require_git_worktree(project)
    policy = execution_policy(args.workspace_write)
    subscription_auth = verify_subscription_auth(args.claude_bin, project)

    team = args.team
    from_agent = args.from_agent
    if not team or not from_agent:
        inferred_team, inferred_agent = infer_identity(project, agmsg_dir)
        team = team or inferred_team
        if not from_agent:
            from_agent = (
                inferred_agent
                if inferred_agent.endswith("-delegate")
                else f"{inferred_agent}-delegate"
            )
    to_agent = args.to_agent
    validate_route_id("team", team)
    validate_route_id("from_agent", from_agent)
    validate_route_id("to_agent", to_agent)
    request = {
        "type": "delegate_request",
        "job_id": job_id,
        "delegate_version": DELEGATE_VERSION,
        "contract_version": CONTRACT_VERSION,
        "model": model,
        "role": role,
        "task": args.task,
        "execution_mode": policy["execution_mode"],
        "tools": policy["tools"],
        "permission_mode": policy["permission_mode"],
        "review_required": policy["review_required"],
        "billing_mode": subscription_auth["billing_mode"],
        "auth_method": subscription_auth["auth_method"],
        "api_provider": subscription_auth["api_provider"],
        "subscription_type": subscription_auth["subscription_type"],
        "requested_by": from_agent,
        "created_at": now_iso(),
    }
    envelope = json.dumps(request, ensure_ascii=False, separators=(",", ":"))

    if args.dry_run:
        return emit(
            {
                "job_id": job_id,
                "status": "dry_run",
                "delegate_version": DELEGATE_VERSION,
                "contract_version": CONTRACT_VERSION,
                "team": team,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "agmsg_reader": agmsg_reader,
                "request": request,
                "claude_policy": {
                    "safe_mode": True,
                    "execution_mode": policy["execution_mode"],
                    "tools": policy["tools"],
                    "permission_mode": policy["permission_mode"],
                    "review_required": policy["review_required"],
                    "workspace_grounding_required": True,
                    "subscription_only": True,
                    "auth_method": subscription_auth["auth_method"],
                    "api_provider": subscription_auth["api_provider"],
                    "subscription_type": subscription_auth["subscription_type"],
                },
            }
        )

    path = state_path(state_dir, job_id)
    if path.exists():
        raise DelegateError(f"job_id already exists; collect it instead of re-running: {job_id}")

    send_message(agmsg_dir, team, from_agent, to_agent, envelope)
    message_id, verified_request = find_job_message(
        list_messages(agmsg_dir, team, to_agent),
        job_id,
        from_agent,
        to_agent,
        "delegate_request",
    )
    state: dict[str, Any] = {
        "job_id": job_id,
        "status": "queued",
        "delegate_version": DELEGATE_VERSION,
        "contract_version": CONTRACT_VERSION,
        "worker_stage": "queued",
        "model": model,
        "role": role,
        "execution_mode": policy["execution_mode"],
        "tools": policy["tools"],
        "permission_mode": policy["permission_mode"],
        "review_required": policy["review_required"],
        "team": team,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "project": str(project),
        "agmsg_dir": str(agmsg_dir),
        "agmsg_reader": agmsg_reader,
        "claude_bin": args.claude_bin,
        "effort": args.effort,
        "billing_mode": subscription_auth["billing_mode"],
        "auth_method": subscription_auth["auth_method"],
        "api_provider": subscription_auth["api_provider"],
        "subscription_type": subscription_auth["subscription_type"],
        "max_message_chars": args.max_message_chars,
        "ttl_seconds": args.ttl,
        "request_message_id": message_id,
        "request": verified_request,
        "created_at": now_iso(),
        "created_epoch": now_epoch(),
        "updated_at": now_iso(),
    }
    write_json_atomic(path, state)
    directory = job_dir(state_dir, job_id)
    stdout_log = open(directory / "worker.stdout.log", "a", encoding="utf-8")
    stderr_log = open(directory / "worker.stderr.log", "a", encoding="utf-8")
    subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_worker",
            "--job-id",
            job_id,
            "--state-dir",
            str(state_dir),
        ],
        stdin=subprocess.DEVNULL,
        stdout=stdout_log,
        stderr=stderr_log,
        start_new_session=True,
        close_fds=True,
    )
    stdout_log.close()
    stderr_log.close()

    final = wait_for_state(state_dir, job_id, args.timeout)
    final = maybe_expire(state_dir, final)
    return emit(public_state(final), 0 if final.get("status") != "failed" else 1)


def collect_main(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir).expanduser().resolve()
    validate_job_id(args.job_id)
    state = wait_for_state(state_dir, args.job_id, args.wait)
    state = maybe_expire(state_dir, state)
    return emit(public_state(state), 0 if state.get("status") != "failed" else 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=DELEGATE_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Send a request, launch Claude, and wait for a correlated response.")
    run.add_argument("--model", required=True, choices=["fable", "sonnet"])
    run.add_argument("--role", choices=["planner", "reviewer", "implementer", "test-planner"])
    run.add_argument("--task", required=True)
    run.add_argument("--job-id")
    run.add_argument("--project", default=os.getcwd())
    run.add_argument("--team")
    run.add_argument("--from-agent")
    run.add_argument("--to-agent", default="claude-delegate")
    run.add_argument("--timeout", type=float, default=60.0)
    run.add_argument("--ttl", type=float, default=3600.0)
    run.add_argument("--effort", choices=["medium", "high", "max"], default="high")
    run.add_argument("--max-task-chars", type=int, default=12000)
    run.add_argument("--max-message-chars", type=int, default=12000)
    run.add_argument("--agmsg-dir", default=str(default_agmsg_dir()))
    run.add_argument("--state-dir", default=str(default_state_dir()))
    run.add_argument("--claude-bin", default="claude")
    run.add_argument(
        "--workspace-write",
        action="store_true",
        help="Allow a Sonnet implementer to edit files in the current Git workspace; Codex review is required.",
    )
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=run_main)

    collect = sub.add_parser("collect", help="Collect a prior job idempotently.")
    collect.add_argument("--job-id", required=True)
    collect.add_argument("--wait", type=float, default=0.0)
    collect.add_argument("--state-dir", default=str(default_state_dir()))
    collect.set_defaults(func=collect_main)

    worker = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("--job-id", required=True)
    worker.add_argument("--state-dir", required=True)
    worker.set_defaults(func=worker_main)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except DelegateError as exc:
        return fail(str(exc), job_id=getattr(args, "job_id", None), code=2)
    except KeyboardInterrupt:
        return fail("interrupted", job_id=getattr(args, "job_id", None), code=130)


if __name__ == "__main__":
    raise SystemExit(main())
