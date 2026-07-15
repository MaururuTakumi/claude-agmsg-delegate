# claude-agmsg-delegate

[日本語](README.ja.md) · [AI instructions](AGENTS.md) · [llms.txt](llms.txt)

[![Tests](https://github.com/MaururuTakumi/claude-agmsg-delegate/actions/workflows/test.yml/badge.svg)](https://github.com/MaururuTakumi/claude-agmsg-delegate/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Codex Skill that delegates bounded planning, review, test planning, and
user-authorized workspace implementation to Claude Fable or Sonnet through
[agmsg](https://github.com/fujibee/agmsg).

It is deliberately headless. You do not need to watch Claude, keep a tmux pane
open, reuse an existing Claude session, or run a monitor. Codex submits one
correlated job and receives or later collects the result. Fable and advisory
Sonnet jobs may read the current project directory with `Read`, `Glob`, and `Grep` in
plan mode; an explicit Sonnet implementation job may edit it and is accepted
only after Codex reviews its diff and runs the relevant tests.

The worker is subscription-only and fail-closed: it runs only when Claude Code reports a paid Claude.ai OAuth session. API keys, bearer-token gateways, custom base URLs, and Bedrock, Vertex, Foundry, or Mantle routes are rejected before inference.

## Give this repository to your AI

Paste this into Codex or another coding agent:

```text
Clone https://github.com/MaururuTakumi/claude-agmsg-delegate into a temporary directory.
Read AGENTS.md and README.md completely.
Run make test and ./install.sh --dry-run.
Confirm that Claude Code is logged in with a paid Claude.ai subscription and that no API-key or cloud-provider credential is active.
Before the final Skill dry-run, verify that ~/.agents/skills/agmsg/scripts/whoami.sh, send.sh, and api.sh exist and are executable. api.sh is agmsg's local read-only JSONL reader, not an Anthropic API call.
If agmsg is missing or outdated, stop and ask me for explicit approval before running npx agmsg, joining a team, or choosing a delivery mode. Do not guess those settings or edit agmsg files directly.
After I approve, install agmsg and change to the target project where delegation will be used. If no teams exist, propose <target-project-name>-team and codex, show both, and wait for my confirmation before join.sh. Ask for delivery separately: recommend 1) turn, allow 2) off, and never choose monitor or both. Empty input or Enter means turn. Use only the provided whoami.sh, join.sh, and delivery.sh procedures. Do not join the temporary Skill clone just to pass verification. Then resume the final dry-run from the target project without invoking a Claude model.
If the checks pass, install the Skill for my current Codex user.
Do not run a Claude model or spend model usage during installation.
Verify the installation with delegate_claude.py --dry-run; this may run the local read-only `claude auth status --json` check, but must not send an agmsg job or run model inference.
Report the resolved route, subscription-only policy, execution mode, tool allowlist, and review requirement. Never display or forward Claude CLI monetary usage estimates.
```

That is the recommended installation path for vibe coders: let your AI inspect, test, install, and verify the repository before using it.

## Requirements

- macOS or Linux
- Python 3.10+
- [Codex](https://github.com/openai/codex)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- A paid Claude Pro, Max, Team, or seat-based Enterprise subscription
- Claude Code authenticated through `claude auth login`, not an API key
- [agmsg](https://github.com/fujibee/agmsg) installed at `~/.agents/skills/agmsg`
- The current project joined to one agmsg team so its team name can be inferred

For strictly zero variable charges, also open Claude **Settings → Usage** and turn **Extra usage / usage credits off**. The wrapper can prove and enforce the active credential route, but the documented Claude CLI does not expose that account-level switch. An already enabled usage-credit setting cannot be disabled by this repository.

Check the local authentication before installation:

```bash
claude auth login
claude auth status --json
```

The wrapper accepts only this shape:

```json
{
  "loggedIn": true,
  "authMethod": "claude.ai",
  "apiProvider": "firstParty",
  "subscriptionType": "max"
}
```

`subscriptionType` may also be `pro`, `team`, or `enterprise`. If `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, a custom Anthropic base URL, a provider-selection variable, or `CLAUDE_CODE_OAUTH_TOKEN` is present, the wrapper stops and tells you to use the local `/login` subscription session instead. It never falls back to a metered credential.

See Anthropic's [authentication precedence](https://code.claude.com/docs/en/authentication), [subscription cost guidance](https://code.claude.com/docs/en/costs), [Pro/Max Claude Code billing explanation](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan), and the current [`claude -p` subscription-usage notice](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan).

## Manual install

agmsg setup changes local agent roles and delivery behavior. If an AI is doing
the setup, it must stop and get your explicit approval before running
`npx agmsg`, joining a team, or selecting a delivery mode.

```bash
# Install agmsg first if needed.
npx agmsg

git clone https://github.com/MaururuTakumi/claude-agmsg-delegate.git
cd claude-agmsg-delegate

make test
./install.sh --dry-run
./install.sh
```

Change back to the project where you want Codex to delegate work before running
the installed-Skill dry-run. Do not join the cloned Skill repository to an
unrelated team merely to satisfy verification.

On a new device with no existing teams, a normal first-time choice is
`<target-project-name>-team / codex` (for example, `movacal-team / codex`). The
agent must display those proposed values and wait for confirmation. After join,
choose `1` or press Enter for the recommended `turn` delivery mode; choose `2`
only for manual `off` delivery. Do not choose `monitor` or `both` for Codex.

Restart Codex so it discovers the new Skill.

## Use it from Codex

Explicit invocation:

```text
$claude-agmsg-delegate Ask Fable to review this architecture.
$claude-agmsg-delegate Ask Sonnet for a bounded implementation and test plan.
$claude-agmsg-delegate Ask Sonnet to implement this bounded change, then review its diff and run tests in Codex.
```

Natural-language requests also match the Skill:

```text
Fableにこの設計をレビューさせて
Sonnetに実装案とテスト案を考えさせて
Sonnetにこの変更を実装させて、Codexでdiffをレビューして
```

The Skill chooses:

- **Fable** for architecture, planning, tradeoffs, and independent critique.
- **Sonnet** for bounded implementation proposals, edge cases, test plans, and
  user-authorized edits in a Git workspace.

Codex remains the orchestrator, diff reviewer, command and test runner,
integrator, and final decision-maker.

## How it works

```text
Codex Desktop
  ├─ preflight: claude auth status --json
  │    └─ require claude.ai + firstParty + paid subscription
  └─ agmsg delegate_request { job_id, model, role, task }
       └─ detached worker
            ├─ repeat the subscription preflight
            ├─ advisory read: Read,Glob,Grep + plan
            ├─ Sonnet implementation: --workspace-write
            │    └─ Read,Edit,Write,Glob,Grep + acceptEdits
            ├─ repeat the auth check after inference; discard on change
            └─ agmsg delegate_response { job_id, status, result }
                 └─ Codex reviews diff, runs tests, and decides
```

agmsg is the job envelope and correlation channel. Authentication and billing are selected by Claude Code. tmux is not part of this execution path, and no existing interactive Claude session is required. The default logical mailboxes are `codex-delegate` and `claude-delegate`, separate from Ghostty/Gdash's visible `codex` and `claude` delivery loops.

The wrapper, not Claude, owns all agmsg I/O. It calls the supported `whoami.sh`,
`send.sh`, and official local read-only `api.sh` scripts. It never reads the
agmsg database or team files directly. `api.sh` emits local JSONL and has no
relationship to Anthropic API access or API billing. Older installations that
already include `list-ids.sh` remain compatible, but fresh installs do not need it.

All jobs run with:

```text
--print --safe-mode --setting-sources "" --output-format json --no-session-persistence
```

Advisory jobs add `--tools "Read,Glob,Grep" --permission-mode plan`. Explicit
Sonnet workspace implementation adds `--tools "Read,Edit,Write,Glob,Grep"
--permission-mode acceptEdits`. Neither mode enables Bash or a permission
bypass.

## CLI

Fable review:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model fable \
  --role reviewer \
  --task "Review this bounded proposal and list its top risks." \
  --timeout 60
```

Sonnet implementation design without edits:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model sonnet \
  --role implementer \
  --task "Propose an implementation plan, edge cases, and tests." \
  --timeout 60
```

Sonnet implementation with local file edits:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model sonnet \
  --role implementer \
  --workspace-write \
  --task "Implement this bounded change in the current Git workspace. Do not touch unrelated files." \
  --timeout 120
```

Before this call, Codex records the current `git status --short`. After it
returns, Codex must inspect `git status --short` and `git diff --`, reject
unrelated edits, and run relevant tests. `--workspace-write` is accepted only
for a Sonnet implementer and only inside a Git worktree.

Validate authentication and routing without sending a message or running model inference:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model fable \
  --task "Review this proposal." \
  --dry-run
```

`--dry-run` executes the local read-only Claude authentication-status command. It does not call a model, create a job state directory, or send an agmsg message.

If the synchronous wait expires, the detached worker continues and returns `status: running`. Collect the same job later instead of launching a duplicate:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" collect \
  --job-id <job_id> \
  --wait 60
```

No always-on monitor is required. The job state is durable, and `collect` is idempotent.

## Result contract

Completed result:

```json
{
  "job_id": "cad-sonnet-20260715T024848Z-a1b2c3",
  "status": "completed",
  "requested_model": "sonnet",
  "actual_model": "claude-sonnet-5",
  "role": "implementer",
  "execution_mode": "workspace_write",
  "tools": ["Read", "Edit", "Write", "Glob", "Grep"],
  "permission_mode": "acceptEdits",
  "review_required": true,
  "billing_mode": "subscription",
  "auth_method": "claude.ai",
  "api_provider": "firstParty",
  "subscription_type": "max",
  "result": "...",
  "elapsed_seconds": 51.2
}
```

The authentication fields come from the worker's subscription checks immediately before and after inference. The wrapper drops Claude CLI monetary usage fields such as `total_cost_usd` and `cost_usd` from its result, agmsg response, saved public state, and terminal output. Codex must not display or paraphrase those estimates; it reports only the verified subscription route.

Timed-out synchronous wait:

```json
{
  "job_id": "cad-sonnet-20260715T024900Z-d4e5f6",
  "status": "running",
  "billing_mode": "subscription",
  "subscription_type": "max",
  "collect_command": "python3 ... collect --job-id ..."
}
```

Jobs are stored under:

```text
~/.cache/codex/claude-agmsg-delegate/jobs/
```

Large results are written to a permission-restricted `result.md`, and the response contains `result_file` instead of placing the entire payload in agmsg.

## Routing

The default route is inferred from the current project using agmsg `whoami.sh`:

```text
<Codex identity>-delegate → <single inferred team> → claude-delegate
```

If the project has multiple identities or teams, routing must be explicit:

```bash
... run \
  --team my-team \
  --from-agent codex-delegate \
  --to-agent claude-delegate \
  --model fable \
  --task "..."
```

The delegate mailbox names are used only for the agmsg request/response record; they do not need visible tmux panes. Pass `--from-agent codex --to-agent claude` only when you intentionally want to share the visible delivery route. The installer never creates, resets, or changes agmsg roles and hooks automatically. Team membership controls message routing, not filesystem scope; the selected project directory and Claude tool policy control read access. Sonnet writes still require a Git worktree.

## Security and billing boundary

- Fable and advisory Sonnet jobs receive only `Read,Glob,Grep` with
  `permission_mode=plan` inside the target project directory. They cannot edit files
  or run commands.
- Explicit Sonnet implementer jobs may edit only the target Git workspace with
  `Read,Edit,Write,Glob,Grep` and `acceptEdits`; Bash is not available.
- Workspace-write output reports `review_required=true`. Codex reviews the
  actual diff, rejects unrelated changes, runs tests, integrates, and makes the
  final decision.
- The parent process checks subscription authentication before agmsg send.
- The detached worker checks it again immediately before inference.
- The worker checks it once more after inference and discards the result if authentication changed.
- API keys, auth tokens, custom base URLs, API-key helpers, and cloud-provider routes fail closed.
- Claude receives a minimal environment allowlist, so unknown future provider variables are not inherited.
- `--safe-mode --setting-sources ""` prevents user, project, and local Claude settings from changing the worker route; admin-managed policy still applies and is covered by the pre/post auth checks.
- There is no API-key or provider fallback when subscription authentication fails or reaches a limit.
- The worker disables the in-CLI usage-credit command and implicit 1M-context variants as defense in depth.
- Account-level Extra usage / usage credits must separately remain off for a zero-variable-charge guarantee.
- Tasks matching common credential patterns are rejected before agmsg send.
- Team and agent identifiers are restricted before reaching older agmsg script versions.
- Shell commands use argument arrays; the Python wrapper never uses `shell=True`.
- The installer does not invoke a model, alter agmsg, or send network requests.
- Workspace-write does not authorize Claude to run commands, install, deploy,
  push, or access unrelated paths.

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

### `subscription-only policy blocked ...`

Unset every reported variable, then authenticate only with the paid Claude.ai account:

```bash
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN
claude auth logout
claude auth login
claude auth status --json
```

Also remove provider-selection variables or an `apiKeyHelper` from Claude settings. The wrapper will not silently choose another billing route.

### Authentication is Claude.ai, but I want zero possible overage

Confirm **Claude Settings → Usage → Extra usage / usage credits** is off. This is separate from the credential-route check. When it is off and included usage is exhausted, wait for the subscription window to reset instead of enabling credits.

### `agmsg identity is ambiguous`

Pass `--team` and `--from-agent` explicitly. The wrapper will not guess between multiple teams or identities.

### `required agmsg script is missing`

Stop before the final dry-run. Do not run a Claude model. The coding agent
should explain that agmsg installation and team/delivery setup change local
agent routing, then ask for explicit approval before running `npx agmsg`.
Official agmsg `api.sh` is the supported local message reader. If it is absent,
update agmsg after approval; do not invent or download a private `list-ids.sh`.

After approval:

1. Run `npx agmsg`.
2. Change to the target project where delegation will actually be used. Do not
   join the temporary Skill clone just to pass verification.
3. Use `~/.agents/skills/agmsg/scripts/whoami.sh` to inspect the target project.
4. If it is not joined, ask for the team and agent names, then use `join.sh`.
   When no teams exist, propose `<target-project-name>-team / codex` and wait
   for confirmation rather than silently creating it.
5. Ask the user to choose `1) turn` (recommended; Enter also selects it) or
   `2) off`, then use `delivery.sh`. Never select `monitor` or `both`, even if
   the raw installer prompt displays them.
6. Resume the same `delegate_claude.py ... --dry-run` verification from the
   target project.

Never edit agmsg config, database, or team files directly, and never guess a
team, identity, or delivery mode. Verify these files exist and are executable:

```text
~/.agents/skills/agmsg/scripts/whoami.sh
~/.agents/skills/agmsg/scripts/send.sh
~/.agents/skills/agmsg/scripts/api.sh
```

### The first-time prompt shows `turn`, `off`, and `monitor`

For this Codex workflow, answer `1` or press Enter to select the recommended
`turn` mode. Use `2` only when you intentionally want manual inbox checks.
`monitor` and `both` are not part of this Skill's setup and must not be selected.

### `status: running`

The synchronous wait ended, not the worker. Use the returned `collect_command`. Do not submit the same task again.

### Claude reports the wrong model

Check `actual_model`, not the requested alias. Treat a mismatch as a failed verification and do not accept the result silently.

## Development

No third-party Python packages are required.

```bash
make test
make check
```

The tests use fake agmsg scripts and a fake Claude executable. They cover
paid-subscription acceptance, API/provider rejection, worker-time authentication
changes, job correlation, timeout collection, large results, Sonnet workspace
edits, the file-tool allowlist, and review-required output. They do not send
live messages, run paid models, or require credentials.

Repository instructions for coding agents are in [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
