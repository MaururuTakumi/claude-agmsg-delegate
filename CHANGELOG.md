# Changelog

## Unreleased

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
