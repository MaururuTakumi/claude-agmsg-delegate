The claim is incorrect: Fable is hard read-only even when labeled
`implementer`. A role does not grant or enable write authority. The wrapper
rejects Fable workspace-write before agmsg send or Claude inference.

The only write-capable Claude path is
`--model sonnet --role implementer --workspace-write`, which receives
`Read,Edit,Write,Glob,Grep` in `acceptEdits` mode. Bash remains unavailable, so
Codex still runs commands and tests, reviews the diff, and makes the final
decision.
