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

5. If the user asked to install, run `./install.sh` only after those checks pass.
6. Verify the installed Skill without invoking Claude:

   ```bash
   python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
     --model fable \
     --task "Installation verification only." \
     --dry-run
   ```

7. Report the resolved team, sender, receiver, model, and `tools: []` policy.

## Do not do these automatically

- Do not invoke Fable or Sonnet during installation or tests.
- Do not spend model credits unless the user explicitly requested a real delegation.
- Do not read or edit the agmsg database, team files, or config directly. Use provided scripts only.
- Do not create, reset, rename, or change agmsg roles or delivery hooks without explicit approval.
- Do not pass secrets, tokens, credentials, private keys, personal data, or raw large logs.
- Do not use `--dangerously-skip-permissions`, enable Claude tools, or weaken `--safe-mode`.
- Do not let delegated Claude edit files, run project commands, deploy, install, push, or make final decisions.
- Do not push, publish, release, or change repository visibility without explicit user authorization.

## Architecture invariants

- Codex is the orchestrator, editor, verifier, and final decision-maker.
- Claude is a bounded advisory worker with no tools.
- The Python wrapper owns all agmsg I/O through `whoami.sh`, `send.sh`, and `list-ids.sh`.
- Every request and response has one stable `job_id`.
- Timeout returns `running`; it does not launch a duplicate job.
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

- Green fixture tests prove wrapper logic, not live Claude authentication or model availability.
- A dry-run proves routing resolution and no-tools policy, not message delivery.
- A completed live job proves one request/response path, not every team or model.
- `requested_model` is not proof of execution model; verify `actual_model`.
