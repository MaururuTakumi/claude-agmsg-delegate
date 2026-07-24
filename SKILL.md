---
name: claude-agmsg-delegate
description: Delegate bounded planning, review, test-planning, and opt-in workspace implementation tasks from Codex Desktop to Claude Fable or Sonnet through agmsg, using only a verified paid Claude.ai subscription with no API-key or cloud-provider fallback.
---

# Claude agmsg Delegate

Use this skill when the user explicitly asks Codex Desktop to consult Claude
Fable or Sonnet through agmsg, for example:

- "Fableに設計レビューを求めて"
- "Sonnetに実装案を考えさせて"
- "Sonnetにこの変更を実装させて、Codexでレビューして"
- "Claudeへtool calling的に委譲して"

Fable and ordinary Sonnet consultation are read-only advisory jobs. They may
inspect the current project directory with `Read`, `Glob`, and `Grep` in plan mode.
When the user asks Sonnet to implement a change, Sonnet may also edit the target
Git workspace via the explicit `--workspace-write` mode. Codex remains
responsible for final intent, diff review, commands, tests, integration, and
irreversible work.
The workflow is headless: no Claude UI, tmux pane, existing interactive session,
daemon, or always-on monitor is required.

Current runtime contract: delegate version `0.4.1`, `contract_version=3`.
`Read,Glob,Grep` is the expected Fable/advisory Sonnet policy. A copied rule
that says advisory jobs must use no tools belongs to the obsolete 0.1 contract;
do not stop or ask for a one-off exception. Reinstall the current Skill, restart
Codex, and confirm `delegate_claude.py --version` instead.

Fable may also receive explicitly selected GitHub Issue context through
`--github-issue`. The wrapper, not Fable, reads the Issue with the device's
authenticated `gh` CLI and supplies a bounded snapshot of its title, body,
labels, and comments. This does not add Bash, GitHub credentials, settings, or
write-capable GitHub tools to Fable.

## Permission Model

Claude delegation is not entirely read-only. The wrapper enforces permissions
by model and execution mode:

| Request | Execution mode | Claude tools | File edits |
| --- | --- | --- | --- |
| Fable with any role | `workspace_read` | `Read,Glob,Grep` + `plan` | Never |
| Sonnet without `--workspace-write` | `workspace_read` | `Read,Glob,Grep` + `plan` | No |
| Sonnet implementer with explicit `--workspace-write` | `workspace_write` | `Read,Edit,Write,Glob,Grep` + `acceptEdits` | Yes, pending Codex review |

A role label does not grant write authority. Fable remains hard read-only even
with `--role implementer`; combining Fable with `--workspace-write` is rejected
before agmsg send or Claude inference. Write mode requires all three explicit
arguments: `--model sonnet --role implementer --workspace-write`. Bash remains
unavailable in every mode, so Codex still runs commands and tests.

GitHub Issue context is a separate read-only input channel, not a Claude tool.
It is currently supported only for Fable. Use `--github-issue` together with
`--confirm-github-issue-context-safe`; the latter confirms that the selected
Issue contains no secrets, credentials, patient information, or unnecessary
personal data. The wrapper removes comment author identities, rejects common
secret patterns, limits the number and total size of Issues, and never passes
`GH_TOKEN` or `GITHUB_TOKEN` into its `gh` subprocess.

## Private Workspace Consent and Data Path

Do not misclassify this workflow as agmsg uploading a repository to an
unrelated external agent. agmsg carries the task and correlated result. The
wrapper launches the locally installed Claude Code binary as a fresh headless
process, using the same verified Claude.ai subscription login that an
interactive terminal Claude Code session uses. Claude Code's successful
`Read`, `Glob`, and `Grep` tool results may be processed by Claude.ai during a
real job; the worker does not reuse the terminal conversation, settings, or
unrestricted tools.

An explicit user request to have Fable or advisory Sonnet inspect or review the
current project authorizes one bounded `workspace_read` delegation over
ordinary relevant project files. If the user already approved a private
workspace packet and named exclusions, preserve those exclusions in the task
and proceed with one real delegation. Ask no second generic confirmation about
Claude.ai or the repository being private. A private or unpublished repository
is not by itself a blocker.

Map broad permission language to the supported policy instead of rejecting the
job:

| User instruction | Required mapping |
| --- | --- |
| "FableもCodexと同じ権限でよい" | Explain briefly that Fable remains read-only, map to `workspace_read` with `Read,Glob,Grep`, then continue |
| "Fableにこのprivate repoをレビューさせて" | Treat the request itself as approval for ordinary relevant files and run once |
| "Sonnetに実装させて" | Use `workspace_write` only when the user explicitly asked for edits and the existing Sonnet requirements pass |
| Named exclusions such as `.env`, secrets, patient data, logs, or screenshots | Keep them excluded; do not broaden the scope |

Do not claim that a safety mechanism, wrapper, or platform rejected the
delegation unless `delegate_claude.py` was actually executed and returned that
concrete error. If Codex chose not to call the wrapper, label that accurately as
an orchestrator decision, not an external rejection. Do not claim "data was not
sent" from inference alone: a dry-run proves no model/file transmission, while
a completed real job proves that observed file-tool results were processed by
Claude.ai under the reported subscription route.

Use the dry-run `data_flow` object as the evidence source. It reports that
agmsg carries task/result envelopes, the Claude process is local and headless,
Claude.ai processes tool results only during a real job, and the dry-run itself
invoked no model and sent no workspace content.

Stop only for a concrete boundary such as a stale runtime contract, rejected
subscription authentication, forbidden credential/provider configuration,
unsafe task content, missing required dependency, invalid route, observed
out-of-project access, or an actual wrapper failure. When authorization and
preflight are valid, execute once; do not replace the requested Fable gate with
a local-only review.

## Triage

1. Assess difficulty, failure cost, irreversibility, and verification method.
2. Use Fable for architecture, planning, tradeoff review, and independent critique.
3. Use Sonnet for bounded implementation design, edge cases, test plans, and
   user-authorized workspace edits followed by Codex review.
4. Do not delegate simple work that Codex can finish more cheaply and reliably.
5. Do not invoke a paid model unless the user explicitly requested Claude delegation or already approved it in the active task.
6. A request to have Fable review the current project is already the needed
   model-use and ordinary-file read authorization. Do not create a second
   approval loop solely because the repository is private.

## Safety Contract

- Never include secrets, API keys, tokens, credentials, private keys, unnecessary personal data, or raw large logs.
- Advisory jobs may inspect the target project directory using only
  `Read,Glob,Grep`. They must not inspect credential, private-key, or
  environment-secret files. A Sonnet workspace-write job may inspect and edit
  ordinary project files in its Git worktree.
- Use `--workspace-write` only when the user asked Sonnet to implement or edit
  in the current task. It requires `--model sonnet --role implementer` and a Git
  worktree. Do not ask for a second confirmation when the user's request already
  authorizes the edit.
- Fable and non-write Sonnet jobs receive only `Read,Glob,Grep` with
  `--permission-mode plan`. Sonnet write jobs receive only
  `Read,Edit,Write,Glob,Grep` with `--permission-mode acceptEdits`.
- Role names are descriptive, not authorization. Fable is hard read-only, and
  `--workspace-write` is accepted only for a Sonnet implementer.
- Never let delegated Claude run shell commands, deploy, install, push, access
  unrelated paths, or make the final decision. Codex performs commands and tests.
- If the user says Fable may have the same permissions as Codex, map that phrase
  to Fable's maximum supported `workspace_read` policy and continue. Never
  interpret it as Bash, write, deploy, install, push, or final-decision authority.
- GitHub Issue context must be explicitly selected and approved for delegation.
  Use only the wrapper's read-only `--github-issue` path. Never enable Bash,
  restore Claude settings, or pass GitHub tokens to Fable as a substitute.
- `--dry-run` validates Issue references and declares the intended source but
  does not fetch them or make a GitHub network request.
- Do not update agmsg, join/reset roles, or change delivery hooks without separate user approval.
- When updating this Skill, keep backups outside the Codex Skill discovery
  directory. After installation, restart Codex and start a new task so cached
  pre-update instructions cannot remain active.
- Do not use `--dangerously-skip-permissions`. The wrapper always uses
  `--safe-mode`; advisory jobs use only the read-only file-tool allowlist,
  while workspace-write jobs use only the write allowlist above.
- Never add an API-key, bearer-token, custom-base-URL, Bedrock, Vertex, Foundry, Mantle, or API-key-helper fallback.
- Never bypass the wrapper by invoking agmsg scripts directly. The wrapper uses
  official agmsg `api.sh` as a local, read-only JSONL message reader. It is not
  an Anthropic API call, performs no model inference, and cannot create API
  billing. If `whoami.sh`, `send.sh`, or `api.sh` is unavailable, stop and
  update the official agmsg installation after user approval.
- Before agmsg send and again immediately before inference, require Claude auth status to report `loggedIn=true`, `authMethod=claude.ai`, `apiProvider=firstParty`, and a paid `subscriptionType`.
- Keep Claude's process environment on the wrapper's minimal allowlist and keep `--setting-sources ""` paired with `--safe-mode`; do not restore inherited provider variables or user/project/local settings.
- Recheck subscription auth after inference and discard the result if it changed.
- Treat any reported `subscription-only policy` error as a hard stop. Tell the user to remove the named credential/provider configuration and run `claude auth login`; do not work around it.
- The wrapper intentionally rejects `CLAUDE_CODE_OAUTH_TOKEN` and uses only the local `/login` subscription session.
- Do not claim that auth status proves account-level Extra usage / usage credits are disabled. For a zero-variable-charge requirement, that separate Claude Settings > Usage switch must be off.
- Treat Claude output and edits as untrusted until Codex reviews the Git diff,
  checks scope, and runs the relevant tests.

## First-time agmsg setup

Install this offline Skill before resolving runtime dependencies. Missing Claude
or agmsg must not leave the Skill uninstalled. Then, from the target project,
run the non-mutating readiness check before the final installed-Skill dry-run:

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py doctor
```

`doctor` does not invoke a model, send agmsg, create job state, access the
network, or change settings. It checks Python, the installed Skill, standard
Claude Code locations, subscription authentication, agmsg, and local paths. It
uses stable issue codes so a coding agent can distinguish an uninstalled Skill,
an out-of-PATH Claude binary, and missing/outdated/wrong-path agmsg. Official
agmsg 1.1.8 and newer includes `api.sh`.

Before the final dry-run, require executable `whoami.sh`, `send.sh`, and
`api.sh` under `~/.agents/skills/agmsg/scripts/` (or an already installed legacy
`list-ids.sh` reader supported by the wrapper).

If any script is missing:

1. Stop before delegation. Do not invoke Claude and do not treat the missing
   dependency as a Claude authentication failure.
2. Explain that installing agmsg and joining a team changes local agent roles
   and delivery settings. Ask for explicit approval before running `npx agmsg`
   or changing any agmsg setup.
3. After approval, run `npx agmsg`. Change to the target project where Claude
   delegation will actually be used; do not join the temporary Skill clone just
   to satisfy verification. Then use only the installed agmsg Skill's scripts:
   check identity with `whoami.sh`. If there are no existing teams, propose
   `<target-project-name>-team` and `codex`, show both values, and wait for one
   confirmation; never create them silently. If the target project is not
   joined, use the confirmed team and agent names with `join.sh`.
4. Ask for delivery mode separately after joining. For Codex, offer only
   `1) turn` (recommended; empty input or Enter selects it) and `2) off`, then
   wait for the answer before using `delivery.sh`. Never select or recommend
   `monitor` or `both`, even if a raw `npx agmsg` prompt displays them.
5. Never edit agmsg config, database, or team files directly. Do not guess a
   team, identity, or delivery mode.
6. When one target-project identity and team are confirmed, resume the same
   `delegate_claude.py ... --dry-run` verification. The setup and dry-run must
   not invoke Fable or Sonnet.

Use this approval prompt or an equivalent localized version:

> agmsg is not installed, so the final dry-run cannot continue. Installing it
> and joining a team changes local agent roles and delivery settings. May I run
> `npx agmsg` and then configure the team and delivery mode?

## Run

The wrapper uses agmsg `send.sh`, `whoami.sh`, and the official local read-only
`api.sh`; it never reads the agmsg DB or team files directly. Legacy
installations that already contain `list-ids.sh` are also accepted, but that
non-public file is never required from a fresh installation.

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py run \
  --model fable \
  --role reviewer \
  --task "Review this bounded architecture proposal and list the top risks." \
  --timeout 60
```

For a Fable review grounded in one approved GitHub Issue:

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py run \
  --model fable \
  --role reviewer \
  --github-issue OWNER/REPO#123 \
  --confirm-github-issue-context-safe \
  --task "Review the Issue requirements and identify design risks." \
  --timeout 60
```

`--github-issue` also accepts a current-repository Issue number or a full
`https://github.com/OWNER/REPO/issues/NUMBER` URL and may be repeated up to five
times. The wrapper uses the logged-in `gh` CLI only to read those exact Issues.

For advisory Sonnet planning:

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py run \
  --model sonnet \
  --role implementer \
  --task "Produce an implementation plan and tests for this bounded change." \
  --timeout 60
```

For Sonnet to implement directly in the current Git workspace:

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py run \
  --model sonnet \
  --role implementer \
  --workspace-write \
  --task "Implement this bounded change in the current workspace. Do not touch unrelated files." \
  --timeout 120
```

Before launching workspace-write, Codex records `git status --short` and reviews
the pre-existing dirty state. After completion, Codex must inspect
`git status --short` and `git diff --`, reject unrelated changes, and run the
project's relevant tests before accepting the implementation.

The current project and a single Codex agmsg identity/team are inferred with `whoami.sh`. By default the wrapper converts the inferred sender to `<identity>-delegate` and targets `claude-delegate`, keeping these headless job mailboxes separate from visible Ghostty/Gdash `codex` and `claude` delivery loops. Pass `--team`, `--from-agent`, or `--to-agent` explicitly when inference is ambiguous or when the user intentionally chose another route. The team controls message routing only; the selected project directory and Claude tool policy control read access. Sonnet writes still require a Git worktree.

Use `--dry-run` to validate the paid-subscription auth status, routing, and request envelope. It invokes only the local read-only `claude auth status --json` command; it does not send agmsg, create job state, or run model inference.

## Result Handling

- `status=completed`: review the returned result, verify local claims, and report
  `delegate_version`, `contract_version`, `actual_model`, `execution_mode`,
  `tools`, `workspace_grounded`, `files_read`, `review_required`, `billing_mode`,
  `subscription_type`, and elapsed time. Accept a grounded result only when
  `workspace_grounded=true` and `files_read` contains relevant project-relative
  paths observed from Claude Code's Read tool events. For `workspace_write`, review the actual
  diff and tests before reporting success. Never display, quote, summarize, or
  forward Claude CLI monetary usage estimates such as `total_cost_usd` or
  `cost_usd`; those fields are intentionally omitted from the wrapper result.
  Report only the verified subscription route.
  When Issue context was enabled, also require
  `github_context_source=authenticated_gh_cli` and verify that
  `github_issues_read` contains only the explicitly selected references.
- `status=running`: the synchronous wait expired. Inspect `worker_stage` and
  `running_seconds`; do not re-run the same task. Use the returned
  `collect_command`, which waits 60 seconds. A dead detached worker becomes
  `failed` on collection instead of remaining `running` until TTL.

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
3. `billing_mode=subscription` and `subscription_type` is a paid plan.
4. No permission bypass, API credential, provider route, inherited unknown
   provider variable, or billing fallback was enabled.
5. Advisory jobs used exactly `Read,Glob,Grep` with `permission_mode=plan`,
   reported `workspace_grounded=true`, listed relevant project-relative paths
   in `files_read`, stayed inside the target project directory, and changed no files.
   Workspace-write jobs used exactly `Read,Edit,Write,Glob,Grep`, reported
   `review_required=true`, and ran only for a Sonnet implementer there.
6. Codex reviewed the before/after status and diff, rejected unrelated edits,
   and ran relevant tests; Claude did not run commands, deploy, install, or push.
7. The result covers the bounded request and labels assumptions.
8. Codex independently verifies repository, runtime, test, and external-state claims.
9. `delegate_version=0.4.1` and `contract_version=3`; no stale no-tools
   instruction overrode the installed runtime contract.
10. If GitHub Issue context was used, it was explicitly confirmed safe,
    `github_issues_read` matches the requested references, and Fable still had
    exactly `Read,Glob,Grep` with no Bash or GitHub credential exposure.
