# AGENTS.md

Instructions for any coding agent that clones this repository.

## First actions

Do these in order before proposing changes or installing anything:

1. Read `README.md`, `SKILL.md`, and this file completely.
2. Confirm the real repository root with `git rev-parse --show-toplevel`.
3. Run `git status -sb` and preserve unrelated user changes.
4. Run the deterministic checks:

   ```bash
   make test
   ./install.sh --dry-run
   ```

5. If the user asked to install this Skill, run `./install.sh` now. The installer
   is offline and does not need Claude or agmsg. Missing runtime dependencies
   must not leave the Skill uninstalled. Use `--force` only for an existing
   installation after reviewing the dry-run.
6. Change to the target project where delegation will actually be used. Do not
   join this temporary Skill clone to a team merely to make verification pass.
   Run the installed, non-mutating readiness check:

   ```bash
   python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" doctor
   ```

   `doctor` may execute the read-only local `claude auth status --json` command.
   It does not invoke a model, send agmsg, create job state, make a network
   request, or change local settings. It automatically checks PATH plus standard
   local Claude Code locations and distinguishes missing, outdated, legacy, and
   wrong-path agmsg installations using stable issue codes.
7. If any required agmsg script is missing, stop and ask for explicit approval
   before running `npx agmsg`. Explain that installation, team joining, and
   delivery-mode selection change local agent routing. After approval, install
   with `npx agmsg`, use the installed agmsg Skill's `whoami.sh`, `join.sh`, and
   `delivery.sh` procedures from the target project, and never edit its config,
   database, or team files directly. If no teams exist, propose
   `<target-project-name>-team` and agent `codex`, display both values, and wait
   for confirmation before `join.sh`; never create them silently. If the target
   project is unknown, ask the user.
   `api.sh` is agmsg's official local, read-only JSONL interface, included in
   official agmsg 1.1.8 and newer. It reads the local agmsg store and is not an
   Anthropic API or a metered model call.
8. After joining, ask for delivery mode separately. Offer only `1) turn`
   (recommended; empty input or Enter selects it) and `2) off`. Wait for the
   answer, then use `delivery.sh`. Never select or recommend `monitor` or
   `both`, even if `npx agmsg` displays them.
9. Verify the installed Skill without running Claude model inference:

   ```bash
   python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" --version
   python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
     --model fable \
     --task "Installation verification only." \
     --dry-run
   ```

   This dry-run may execute the read-only local `claude auth status --json`
   command. It must not send agmsg, create job state, or run a model.

10. Require delegate version `0.4.0` and `contract_version=3`, then report the resolved Claude binary, team, sender, receiver, model,
   `billing_mode: subscription`, paid `subscription_type`, execution mode,
   tool allowlist, and review requirement.

If agmsg was initially missing, resume this same final dry-run after its setup;
do not invoke Fable or Sonnet during dependency installation or verification.

## Do not do these automatically

- Do not invoke Fable or Sonnet during installation or tests.
- Do not run `npx agmsg`, join a team, or select a delivery mode without
  explicit approval.
- Do not enable agmsg `monitor` or `both` for this Codex workflow.
- Do not spend model credits unless the user explicitly requested a real delegation.
- Do not read or edit the agmsg database, team files, or config directly. Use provided scripts only.
- Do not create, reset, rename, or change agmsg roles or delivery hooks without explicit approval.
- Do not pass secrets, tokens, credentials, private keys, personal data, or raw large logs.
- Do not use `--github-issue` until the selected Issue is explicitly confirmed
  free of secrets, credentials, patient information, and unnecessary personal
  data. The wrapper's secret-pattern rejection does not replace that review.
- Do not use `--dangerously-skip-permissions` or weaken `--safe-mode`.
- Do not add API-key, bearer-token, custom-base-URL, API-key-helper, Bedrock, Vertex, Foundry, Mantle, or other pay-as-you-go fallback paths.
- Do not bypass `delegate_claude.py` by invoking agmsg scripts directly. The
  wrapper may use official agmsg `api.sh` only for local, read-only message
  correlation; this is unrelated to Anthropic API billing.
- Do not display, quote, summarize, or forward Claude CLI monetary usage
  estimates such as `total_cost_usd` or `cost_usd`. Report only the verified
  subscription route.
- Do not bypass the exact Claude.ai subscription auth preflight or remove its worker-side recheck.
- Do not claim that Claude auth status proves the separate account-level Extra usage / usage-credits switch is off.
- Do not enable workspace writes unless the user asked Sonnet to implement or
  edit in the current task. Never let delegated Claude run project commands,
  deploy, install, push, access unrelated paths, or make final decisions.
- Do not push, publish, release, or change repository visibility without explicit user authorization.

## Architecture invariants

- Codex is the orchestrator, diff reviewer, command runner, test runner,
  integrator, and final decision-maker.
- Fable and advisory Sonnet jobs may read only the target project directory using
  `Read,Glob,Grep` with `--permission-mode plan`. An explicit Sonnet implementer
  workspace-write job may use only `Read,Edit,Write,Glob,Grep` with
  `--permission-mode acceptEdits` there.
- A role label does not grant write authority. Fable is hard read-only even when
  labeled `implementer`; Fable workspace-write requests stop before agmsg send.
  Only `--model sonnet --role implementer --workspace-write` enables file edits.
- The runtime prompt requires at least one relevant `Read` call. Claude Code
  runs with verbose `stream-json`; the wrapper accepts a result only when it
  observes project-contained Read evidence and returns project-relative
  `files_read` with `workspace_grounded=true`.
- Optional Fable GitHub Issue context is fetched by the wrapper with an
  authenticated `gh issue view` call for only the explicitly selected Issues.
  It does not add Bash or GitHub tools to Claude, strips comment author
  identities, excludes token environment variables, and is never fetched by
  `--dry-run`.
- Workspace-write responses set `review_required=true`. Codex must compare the
  pre-existing status with the resulting `git status --short` and `git diff --`,
  reject unrelated edits, and run relevant tests before acceptance.
- The only allowed Claude credential route is a local paid Claude.ai `/login` OAuth session: `loggedIn=true`, `authMethod=claude.ai`, `apiProvider=firstParty`, and a paid `subscriptionType`.
- API/provider environment variables fail closed before agmsg send. Authentication is checked again immediately before inference, with no fallback.
- Claude receives a minimal environment allowlist and `--safe-mode --setting-sources ""`; user, project, and local settings must not be re-enabled.
- Authentication is checked after inference too; a changed route quarantines the result as failed.
- No Claude UI, tmux pane, existing interactive session, daemon, or always-on monitor is required.
- Default agmsg mailboxes remain `<inferred-agent>-delegate` and `claude-delegate`; do not reuse visible `codex`/`claude` loops unless explicitly requested.
- agmsg team membership controls message routing, not filesystem scope. The
  selected project directory and Claude tool/permission policy control read
  access; workspace writes still require a Git worktree.
- The Python wrapper owns all agmsg I/O through `whoami.sh`, `send.sh`, and the
  official local read-only `api.sh`. Existing pre-release installations with
  `list-ids.sh` remain supported, but a fresh install never requires that file.
- Installer backups live under
  `<codex-home>/skill-backups/claude-agmsg-delegate/`, outside `skills/`.
  Old installer-created `skills/claude-agmsg-delegate.backup-*` directories are
  moved there intact. Unknown duplicate Skills are listed and stop readiness
  verification; they are never deleted or moved automatically.
- Monetary usage metadata from Claude CLI is excluded from agmsg responses,
  saved public state, and terminal output.
- Every request and response has one stable `job_id`.
- Timeout returns `running`; it does not launch a duplicate job.
- Running output includes `worker_stage` and `running_seconds`; collection marks
  a dead worker failed immediately instead of waiting for the full TTL.
- `collect` is idempotent.
- Large results spill to a permission-restricted job-local file.
- Shell commands use argument arrays. Never introduce `shell=True`.
- Route identifiers remain strictly validated before reaching agmsg scripts.

## Change procedure

1. Keep each change narrow.
2. Update or add a fixture test for every behavior change.
3. Run `make test`.
4. Run the sensitive-data scan from `Makefile` with `make check`.
5. If changing `SKILL.md`, update the relevant eval case and compare baseline/candidate scores.
6. Never claim live agmsg or Claude behavior from fixture tests alone.

## Proof boundaries

- Green fixture tests prove wrapper logic, not live Claude authentication, account billing settings, or model availability.
- A live dry-run proves the current auth-status fields, routing resolution,
  declared tool policy, and contract version, not message delivery, actual file
  reads/edits, review quality,
  or whether account-level Extra usage is disabled.
- A completed live job proves one request/response path, not every team or model.
- `requested_model` is not proof of execution model; verify `actual_model`.
