# Changelog

## Unreleased

## 0.4.0 — 2026-07-24

- Add an explicit Fable `--github-issue` input path backed by the device's
  authenticated `gh issue view` command.
- Keep delegated Claude on `Read,Glob,Grep` with no Bash, inherited settings,
  GitHub credentials, or write-capable GitHub tools.
- Add safe-context confirmation, common-secret rejection, author-identity
  omission, reference/count/size limits, and untrusted-context framing.
- Preserve dry-run's no-network guarantee: Issue references are validated and
  declared but not fetched.
- Add fixture coverage for Issue ingestion, token-environment isolation,
  secret rejection, and unchanged Fable tool permissions.

## 0.3.1 — 2026-07-24

- Add an explicit permission matrix clarifying that Fable is hard read-only,
  advisory Sonnet is read-only, and only an explicitly authorized Sonnet
  implementer may edit through `--workspace-write`.
- Clarify that a role label never grants write authority, Fable workspace-write
  requests stop before agmsg send, and Bash remains unavailable in every mode.
- Add regression coverage for Fable carrying the `implementer` role without
  gaining write access.

## 0.3.0 — 2026-07-21

- Install the offline Codex Skill before stopping for Claude or agmsg runtime setup.
- Support and continuously test Python 3.9, including stock macOS Python 3.9.6.
- Discover Claude Code deterministically from PATH and standard local install paths,
  then pin the resolved absolute path for detached workers.
- Add a non-mutating `doctor` command with stable issue codes for Skill,
  Python, Claude subscription authentication, agmsg, and local path readiness.
- Diagnose pre-1.1.8 agmsg installs that lack official `api.sh` separately from
  missing, non-executable, legacy, and alternate-path installations.

## 0.2.1 — 2026-07-20

- Move update backups outside Codex's `skills/` discovery directory.
- Migrate installer-created `claude-agmsg-delegate.backup-*` directories to the
  new backup root without deleting or overwriting them.
- Stop installation readiness when an unrelated same-name Skill remains, and
  list every conflicting path and version.
- Tell users to restart Codex and start a new task after updating.
- Add macOS/Linux-compatible installer regression coverage for fresh installs,
  forced updates, old-layout migration, collisions, dry-run, and unknown
  duplicate Skills.

## 0.2.0 — 2026-07-15

- Require and verify an observed Claude Code `Read` event before accepting a
  delegated result; return project-relative `files_read` and
  `workspace_grounded=true`.
- Switch worker output to verbose `stream-json` so file-tool evidence can be
  extracted without exposing raw transcripts or monetary metadata.
- Add `delegate_version`, `contract_version`, `worker_stage`, running duration,
  and immediate dead-worker detection on collection.
- Make the installed version directly testable and copy `VERSION` into the
  installed Skill.

- Require a verified paid Claude.ai subscription before agmsg send and again immediately before inference.
- Reject API-key, bearer-token, custom-base-URL, and cloud-provider billing routes with no fallback.
- Remove dollar-budget and estimated-cost fields that could be mistaken for subscriber billing.
- Use official agmsg `api.sh` as the local read-only JSONL reader while
  suppressing Claude CLI monetary usage estimates from user-facing output and
  stored responses.
- Allow Fable and advisory Sonnet to inspect the target project directory with
  `Read,Glob,Grep` under `--permission-mode plan`, while keeping edits and Bash
  disabled.
- Document headless operation: no Claude UI, tmux pane, existing session, daemon, or monitor is required.
- Add fixture coverage for provider rejection, logged-out/non-subscription auth, and worker-time auth changes.
- Accept both raw and caret-escaped agmsg separators for SQLite CLI 3.50+ compatibility.
- Minimize Claude's inherited environment, disable user/project/local setting sources, and quarantine results when the post-inference auth check changes.
- Default to headless `*-delegate` agmsg mailboxes so visible Ghostty/Gdash agent loops do not receive wrapper jobs.
- Add an explicit first-device agmsg prerequisite flow: stop before final dry-run, request approval for `npx agmsg` and routing setup, use only the provided identity/join/delivery scripts from the actual target project, then resume verification without model inference.
- Document the no-existing-team path (`<project>-team / codex`) and constrain Codex delivery setup to confirmed `turn` or `off`, excluding the experimental `monitor`/`both` modes.
- Add an explicit Sonnet-only `--workspace-write` mode with `Read,Edit,Write,Glob,Grep`, `acceptEdits`, Git-worktree validation, and mandatory Codex diff review.

## 0.1.0 — 2026-07-15

- Initial public release.
- Fable and Sonnet advisory delegation through agmsg.
- Job-ID correlation, synchronous wait, detached continuation, and idempotent collection.
- No-tools Claude execution with secret and routing guards.
- AI-first installation instructions and no-network fixture tests.
