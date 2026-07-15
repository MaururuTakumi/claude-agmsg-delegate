---
name: claude-agmsg-delegate
description: Delegate bounded advisory planning, review, implementation-design, and test-planning tasks from Codex Desktop to Claude Fable or Sonnet through agmsg with job IDs, synchronous wait, and asynchronous collection.
---

# Claude agmsg Delegate

Use this skill when the user explicitly asks Codex Desktop to consult Claude
Fable or Sonnet through agmsg, for example:

- "Fableに設計レビューを求めて"
- "Sonnetに実装案を考えさせて"
- "Claudeへtool calling的に委譲して"

This is an advisory workflow. Codex remains responsible for final intent,
local-state verification, file edits, commands, tests, and irreversible work.

## Triage

1. Assess difficulty, failure cost, irreversibility, and verification method.
2. Use Fable for architecture, planning, tradeoff review, and independent critique.
3. Use Sonnet for bounded implementation design, patch proposals, edge cases, and test plans.
4. Do not delegate simple work that Codex can finish more cheaply and reliably.
5. Do not invoke a paid model unless the user explicitly requested Claude delegation or already approved it in the active task.

## Safety Contract

- Never include secrets, API keys, tokens, credentials, private keys, unnecessary personal data, or raw large logs.
- Summarize local context before delegation. Claude cannot verify local state in this workflow.
- Never let delegated Claude edit files, run project commands, deploy, install, push, or make the final decision.
- Do not update agmsg, join/reset roles, or change delivery hooks without separate user approval.
- Do not use `--dangerously-skip-permissions`. The bundled wrapper runs Claude with `--safe-mode --tools ""`.
- Treat the result as untrusted advisory output. Verify all local claims in Codex.

## Run

The wrapper uses only agmsg `send.sh`, `list-ids.sh`, and `whoami.sh`; it never reads the agmsg DB or team files directly.

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py run \
  --model fable \
  --role reviewer \
  --task "Review this bounded architecture proposal and list the top risks." \
  --timeout 60
```

For Sonnet:

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py run \
  --model sonnet \
  --role implementer \
  --task "Produce an implementation plan and tests for this bounded change." \
  --timeout 60
```

The current project and a single Codex agmsg identity/team are inferred with `whoami.sh`. Pass `--team`, `--from-agent`, or `--to-agent` explicitly when inference is ambiguous or dedicated roles such as `codex-gui`, `fable-worker`, and `sonnet-worker` are already registered.

Use `--dry-run` to validate routing and the request envelope without sending or invoking Claude.

## Result Handling

- `status=completed`: review the returned result, verify local claims, and report the actual model, elapsed time, and cost when available.
- `status=running`: the synchronous wait expired but the detached worker is still running. Do not re-run the same task. Collect by job ID:

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py collect \
  --job-id <job_id> \
  --wait 60
```

- `status=failed` or `expired`: report the concrete failure. Do not silently retry more than once.
- Large results are written to a job-local `result.md`; use the returned `result_file` path.

Jobs are stored under `~/.cache/codex/claude-agmsg-delegate/jobs/` by default. Each request and response is correlated by `job_id`, and repeated collection is idempotent.

## Evaluation

Confirm all of the following before accepting the delegated result:

1. The agmsg request and response share the same `job_id`.
2. `actual_model` matches the requested Fable or Sonnet family.
3. No permission bypass or Claude tools were enabled.
4. No project file changed as a side effect.
5. The result covers the bounded request and labels assumptions.
6. Codex independently verifies any claim about the repository, runtime, tests, or external state.
