Not all Claude jobs are read-only. Fable is always read-only with
`Read,Glob,Grep` in plan mode, regardless of its role label. Advisory Sonnet
uses the same read-only policy. Only a Sonnet implementer with the explicit
`--workspace-write` flag may edit files, using
`Read,Edit,Write,Glob,Grep` in `acceptEdits` mode. Bash is unavailable in every
mode, so Codex runs commands and tests and reviews the diff.
