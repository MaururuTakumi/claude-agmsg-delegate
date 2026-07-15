# claude-agmsg-delegate

[日本語](README.ja.md) · [AI instructions](AGENTS.md) · [llms.txt](llms.txt)

[![Tests](https://github.com/MaururuTakumi/claude-agmsg-delegate/actions/workflows/test.yml/badge.svg)](https://github.com/MaururuTakumi/claude-agmsg-delegate/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Codex Skill that delegates bounded planning, review, implementation-design, and test-planning work to Claude Fable or Sonnet through [agmsg](https://github.com/fujibee/agmsg).

Codex stays in charge. Claude gets no tools, cannot edit your files, and returns a job-ID-correlated advisory result.

## Give this repository to your AI

Paste this into Codex or another coding agent:

```text
Clone https://github.com/MaururuTakumi/claude-agmsg-delegate into a temporary directory.
Read AGENTS.md and README.md completely.
Run the fixture tests and ./install.sh --dry-run.
If they pass, install the Skill for my current Codex user.
Do not invoke Claude or spend model credits during installation.
Verify the installation with a delegate_claude.py dry-run and report the resolved team, sender, receiver, model, and tools policy.
```

That is the recommended installation path for vibe coders: let your AI inspect, test, install, and verify it.

## Manual install

Requirements:

- macOS or Linux
- Python 3.10+
- [Codex](https://github.com/openai/codex)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [agmsg](https://github.com/fujibee/agmsg) installed at `~/.agents/skills/agmsg`
- One agmsg team containing a Codex sender and Claude receiver

```bash
# Install agmsg first if needed.
npx agmsg

git clone https://github.com/MaururuTakumi/claude-agmsg-delegate.git
cd claude-agmsg-delegate

make test
./install.sh --dry-run
./install.sh
```

Restart Codex so it discovers the new Skill.

## Use it from Codex

Explicit invocation:

```text
$claude-agmsg-delegate Ask Fable to review this architecture.
$claude-agmsg-delegate Ask Sonnet for a bounded implementation and test plan.
```

Natural-language requests also match the Skill:

```text
Fableにこの設計をレビューさせて
Sonnetに実装案とテスト案を考えさせて
```

The Skill chooses:

- **Fable** for architecture, planning, tradeoffs, and independent critique.
- **Sonnet** for bounded implementation proposals, edge cases, and test plans.

Codex still performs all local reads, edits, commands, tests, and final decisions.

## What happens

```text
Codex Desktop
  └─ agmsg delegate_request { job_id, model, role, task }
       └─ detached no-tools Claude worker
            └─ agmsg delegate_response { job_id, status, result }
                 └─ Codex verifies and decides
```

The wrapper, not Claude, owns all agmsg I/O. It calls only the supported `whoami.sh`, `send.sh`, and `list-ids.sh` scripts. It never reads the agmsg database or team files directly.

Claude runs with:

```text
--print --safe-mode --tools "" --output-format json
```

No permission bypass is used.

## CLI

Fable review:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model fable \
  --role reviewer \
  --task "Review this bounded proposal and list its top risks." \
  --timeout 60
```

Sonnet implementation design:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model sonnet \
  --role implementer \
  --task "Propose an implementation plan, edge cases, and tests." \
  --timeout 60
```

Validate routing without sending a message or invoking Claude:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model fable \
  --task "Review this proposal." \
  --dry-run
```

If the synchronous wait expires, the detached worker continues and returns `status: running`. Collect the same job later instead of launching a duplicate:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" collect \
  --job-id <job_id> \
  --wait 60
```

## Result contract

Completed result:

```json
{
  "job_id": "cad-fable-20260715T024848Z-a1b2c3",
  "status": "completed",
  "requested_model": "fable",
  "actual_model": "claude-fable-5",
  "role": "reviewer",
  "result": "...",
  "elapsed_seconds": 51.2,
  "cost_usd": 0.32
}
```

Timed-out synchronous wait:

```json
{
  "job_id": "cad-sonnet-20260715T024900Z-d4e5f6",
  "status": "running",
  "collect_command": "python3 ... collect --job-id ..."
}
```

Repeated collection is idempotent. Jobs are stored under:

```text
~/.cache/codex/claude-agmsg-delegate/jobs/
```

Large results are written to a permission-restricted `result.md`, and the response contains `result_file` instead of placing the entire payload in agmsg.

## Routing

The default route is inferred from the current project using agmsg `whoami.sh`:

```text
<single Codex identity> → <single team> → claude
```

If the project has multiple identities or teams, routing must be explicit:

```bash
... run \
  --team my-team \
  --from-agent codex-gui \
  --to-agent fable-worker \
  --model fable \
  --task "..."
```

Dedicated roles are recommended when the same team also has visible tmux delivery loops. The installer never creates, resets, or changes agmsg roles and hooks automatically.

## Security model

- Claude is advisory and receives no tools.
- Codex remains the editor, command runner, verifier, and final decision-maker.
- Tasks matching common credential patterns are rejected before agmsg send.
- Team and agent identifiers are restricted before reaching older agmsg script versions.
- Shell commands use argument arrays; the Python wrapper never uses `shell=True`.
- The default per-call budget is capped with `--max-budget-usd 1.0`.
- The installer does not invoke Claude, alter agmsg, or send network requests.

Do not delegate secrets, credentials, private keys, unnecessary personal data, or raw large logs. Summarize and redact context first.

## Updating

Pull the repository, rerun tests, then install with backup:

```bash
git pull --ff-only
make test
./install.sh --dry-run --force
./install.sh --force
```

`--force` moves the previous installed Skill to a timestamped backup instead of deleting it.

## Troubleshooting

### `agmsg identity is ambiguous`

Pass `--team` and `--from-agent` explicitly. The wrapper will not guess between multiple teams or identities.

### `required agmsg script is missing`

Install or repair agmsg, then verify these files exist and are executable:

```text
~/.agents/skills/agmsg/scripts/whoami.sh
~/.agents/skills/agmsg/scripts/send.sh
~/.agents/skills/agmsg/scripts/list-ids.sh
```

### `status: running`

The synchronous wait ended, not the worker. Use the returned `collect_command`. Do not submit the same task again.

### Claude reports the wrong model

Check `actual_model`, not the requested alias. Treat a mismatch as a failed verification and do not accept the result silently.

## Development

No third-party Python packages are required.

```bash
make test
```

The tests use fake agmsg scripts and a fake Claude executable. They do not send messages, invoke paid models, or require credentials.

Repository instructions for coding agents are in [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
