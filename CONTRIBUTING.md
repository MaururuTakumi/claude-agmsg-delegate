# Contributing

Thanks for improving `claude-agmsg-delegate`.

## Before opening a pull request

1. Read `AGENTS.md` and preserve its safety invariants.
2. Keep Fable and advisory Sonnet read-only with `Read,Glob,Grep` and plan mode.
   Preserve the explicit Sonnet-only Git workspace-write gate, narrow file-tool
   allowlist, and Codex review requirement.
3. Preserve the paid Claude.ai subscription-only preflight, worker-side recheck, and no-fallback policy.
4. Add or update a fixture test for behavior changes.
5. Run:

   ```bash
   make check
   ./install.sh --dry-run
   ```

6. State clearly whether you ran a live subscription-model test. Fixture tests alone must not be described as live Claude or billing proof.

## Pull request scope

- Keep one behavior change per pull request when practical.
- Do not include credentials, transcripts, agmsg databases, team files, or machine-local paths.
- Do not weaken route validation, secret rejection, job-ID correlation,
  subscription-auth validation, safe mode, the advisory read-only policy, or
  the workspace-write tool boundary without a written security rationale.
- Do not add an API-key, provider, proxy, or usage-credit fallback.
- Do not add direct SQLite access. Use agmsg scripts.
