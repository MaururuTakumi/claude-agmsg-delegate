# Prompt examples

## Install with an AI agent

```text
Clone https://github.com/MaururuTakumi/claude-agmsg-delegate into a temporary directory.
Read AGENTS.md completely, run make test and ./install.sh --dry-run, then install it for my current Codex user if all checks pass. Require paid Claude.ai subscription auth and reject API/provider credentials. Do not run Claude model inference during installation. Verify auth and routing with a dry-run.
```

## Fable architecture review

```text
$claude-agmsg-delegate Ask Fable to review this architecture. Give it only the bounded proposal, required invariants, acceptance criteria, and forbidden actions. Verify any local-state claims yourself.
```

## Sonnet implementation in the workspace

```text
$claude-agmsg-delegate Ask Sonnet to implement this bounded change in the current Git workspace. Keep edits scoped and do not touch unrelated files. After Sonnet finishes, review the Git diff and run the tests in Codex before accepting it.
```
