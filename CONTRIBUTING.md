# Contributing

Thanks for improving `claude-agmsg-delegate`.

## Before opening a pull request

1. Read `AGENTS.md` and preserve its safety invariants.
2. Keep delegated Claude advisory and tool-free.
3. Add or update a fixture test for behavior changes.
4. Run:

   ```bash
   make check
   ./install.sh --dry-run
   ```

5. State clearly whether you ran a live paid-model test. Fixture tests alone must not be described as live Claude proof.

## Pull request scope

- Keep one behavior change per pull request when practical.
- Do not include credentials, transcripts, agmsg databases, team files, or machine-local paths.
- Do not weaken route validation, secret rejection, job-ID correlation, safe mode, or the empty-tools policy without a written security rationale.
- Do not add direct SQLite access. Use agmsg scripts.
