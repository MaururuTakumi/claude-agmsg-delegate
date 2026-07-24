Fable defaults to the reviewer role and uses `Read,Glob,Grep` in plan mode.
Workspace changes use a Sonnet implementer with `--workspace-write` and
`Read,Edit,Write,Glob,Grep`. Codex still runs commands and tests, reviews the
diff, and makes the final decision.
