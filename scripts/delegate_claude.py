#!/usr/bin/env python3
"""Delegate bounded advisory work to Claude through agmsg.

The wrapper owns all agmsg I/O. Claude receives no tools and cannot edit files or
inspect local state. Long calls continue in a detached worker and can be collected
later by job ID.
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


def run_checked(args: list[str], *, timeout: float = 30, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, env=env)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise DelegateError(f"command failed: {Path(args[0]).name}: {redact(detail)}")
    return result


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


def list_messages(agmsg_dir: Path, team: str, to_agent: str, since_id: int = 0) -> list[dict[str, Any]]:
    list_ids = required_script(agmsg_dir, "list-ids.sh")
    output = run_checked([str(list_ids), team, to_agent, "--since-id", str(since_id)]).stdout
    messages: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        messages.append({"id": int(parts[0]), "from": parts[1], "body": parts[2]})
    return messages


def latest_message_id(agmsg_dir: Path, team: str, to_agent: str) -> int:
    messages = list_messages(agmsg_dir, team, to_agent, 0)
    return messages[-1]["id"] if messages else 0


def find_job_message(messages: list[dict[str, Any]], job_id: str, expected_from: str) -> tuple[int, dict[str, Any]]:
    for message in messages:
        if message["from"] != expected_from:
            continue
        try:
            payload = json.loads(message["body"])
        except json.JSONDecodeError:
            continue
        if payload.get("job_id") == job_id:
            return int(message["id"]), payload
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
        "requested_model": state.get("model"),
        "role": state.get("role"),
        "created_at": state.get("created_at"),
        "updated_at": state.get("updated_at"),
    }
    for key in ["actual_model", "result", "result_preview", "result_file", "elapsed_seconds", "cost_usd", "error"]:
        value = response.get(key, state.get(key))
        if value is not None:
            output[key] = value
    output["collect_command"] = (
        f"python3 {Path(__file__).resolve()} collect --job-id {state.get('job_id')}"
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
    return (
        f"You are Claude acting as a bounded advisory {role} for Codex. "
        "You have no tools and must not claim to inspect local state, edit files, run commands, deploy, push, install, or make the final decision. "
        "Label assumptions and return only the requested deliverable.\n\n"
        f"Task retrieved from agmsg job {state['job_id']}:\n{task}"
    )


def claude_command(state: dict[str, Any]) -> list[str]:
    return [
        state["claude_bin"],
        claude_prompt(state),
        "-p",
        "--model",
        state["model"],
        "--effort",
        state["effort"],
        "--safe-mode",
        "--max-budget-usd",
        str(state["max_budget_usd"]),
        "--output-format",
        "json",
        "--tools",
        "",
    ]


def worker_main(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    state = read_state(state_dir, args.job_id)
    state["status"] = "running"
    state["worker_pid"] = os.getpid()
    state["updated_at"] = now_iso()
    write_json_atomic(state_path(state_dir, args.job_id), state)
    started = time.monotonic()
    try:
        command = claude_command(state)
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=float(state["ttl_seconds"]),
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise DelegateError(f"Claude failed: {redact(detail)}")
        try:
            model_output = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise DelegateError(f"Claude returned invalid JSON: {exc}") from exc
        text_result = model_output.get("result")
        if not isinstance(text_result, str) or not text_result.strip():
            raise DelegateError("Claude returned an empty result")

        actual_model = choose_actual_model(model_output.get("modelUsage"), state["model"])
        response: dict[str, Any] = {
            "type": "delegate_response",
            "job_id": state["job_id"],
            "status": "completed",
            "requested_model": state["model"],
            "actual_model": actual_model,
            "role": state["role"],
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "cost_usd": model_output.get("total_cost_usd"),
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

        before = latest_message_id(Path(state["agmsg_dir"]), state["team"], state["from_agent"])
        send_message(
            Path(state["agmsg_dir"]),
            state["team"],
            state["to_agent"],
            state["from_agent"],
            json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        )
        message_id, verified = find_job_message(
            list_messages(Path(state["agmsg_dir"]), state["team"], state["from_agent"], before),
            state["job_id"],
            state["to_agent"],
        )
        state["status"] = "completed"
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
        "requested_model": state["model"],
        "role": state["role"],
        "error": error,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
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
    if now_epoch() - created > ttl and not alive:
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

    team = args.team
    from_agent = args.from_agent
    if not team or not from_agent:
        inferred_team, inferred_agent = infer_identity(project, agmsg_dir)
        team = team or inferred_team
        from_agent = from_agent or inferred_agent
    to_agent = args.to_agent
    validate_route_id("team", team)
    validate_route_id("from_agent", from_agent)
    validate_route_id("to_agent", to_agent)
    if args.timeout < 0:
        raise DelegateError("timeout must be zero or greater")
    if args.ttl <= 0:
        raise DelegateError("ttl must be greater than zero")
    if args.max_budget_usd <= 0:
        raise DelegateError("max_budget_usd must be greater than zero")
    if args.max_task_chars <= 0 or args.max_message_chars <= 0:
        raise DelegateError("max_task_chars and max_message_chars must be greater than zero")
    request = {
        "type": "delegate_request",
        "job_id": job_id,
        "model": model,
        "role": role,
        "task": args.task,
        "requested_by": from_agent,
        "created_at": now_iso(),
    }
    envelope = json.dumps(request, ensure_ascii=False, separators=(",", ":"))

    if args.dry_run:
        return emit(
            {
                "job_id": job_id,
                "status": "dry_run",
                "team": team,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "request": request,
                "claude_policy": {"safe_mode": True, "tools": []},
            }
        )

    path = state_path(state_dir, job_id)
    if path.exists():
        raise DelegateError(f"job_id already exists; collect it instead of re-running: {job_id}")

    before = latest_message_id(agmsg_dir, team, to_agent)
    send_message(agmsg_dir, team, from_agent, to_agent, envelope)
    message_id, verified_request = find_job_message(
        list_messages(agmsg_dir, team, to_agent, before), job_id, from_agent
    )
    state: dict[str, Any] = {
        "job_id": job_id,
        "status": "queued",
        "model": model,
        "role": role,
        "team": team,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "project": str(project),
        "agmsg_dir": str(agmsg_dir),
        "claude_bin": args.claude_bin,
        "effort": args.effort,
        "max_budget_usd": args.max_budget_usd,
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
    return emit(public_state(final), 0 if final.get("status") != "failed" else 1)


def collect_main(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir).expanduser().resolve()
    validate_job_id(args.job_id)
    state = wait_for_state(state_dir, args.job_id, args.wait)
    state = maybe_expire(state_dir, state)
    return emit(public_state(state), 0 if state.get("status") != "failed" else 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Send a request, launch Claude, and wait for a correlated response.")
    run.add_argument("--model", required=True, choices=["fable", "sonnet"])
    run.add_argument("--role", choices=["planner", "reviewer", "implementer", "test-planner"])
    run.add_argument("--task", required=True)
    run.add_argument("--job-id")
    run.add_argument("--project", default=os.getcwd())
    run.add_argument("--team")
    run.add_argument("--from-agent")
    run.add_argument("--to-agent", default="claude")
    run.add_argument("--timeout", type=float, default=60.0)
    run.add_argument("--ttl", type=float, default=3600.0)
    run.add_argument("--effort", choices=["medium", "high", "max"], default="high")
    run.add_argument("--max-budget-usd", type=float, default=1.0)
    run.add_argument("--max-task-chars", type=int, default=12000)
    run.add_argument("--max-message-chars", type=int, default=12000)
    run.add_argument("--agmsg-dir", default=str(default_agmsg_dir()))
    run.add_argument("--state-dir", default=str(default_state_dir()))
    run.add_argument("--claude-bin", default="claude")
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
