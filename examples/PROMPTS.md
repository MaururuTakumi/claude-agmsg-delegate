# Prompt examples

## Install with an AI agent

```text
Clone https://github.com/MaururuTakumi/claude-agmsg-delegate into a temporary directory.
Read AGENTS.md completely, run make test and ./install.sh --dry-run, then install it for my current Codex user if all checks pass. Do not invoke Claude during installation. Verify with a dry-run.
```

## Fable architecture review

```text
$claude-agmsg-delegate Ask Fable to review this architecture. Give it only the bounded proposal, required invariants, acceptance criteria, and forbidden actions. Verify any local-state claims yourself.
```

## Sonnet implementation proposal

```text
$claude-agmsg-delegate Ask Sonnet for an implementation proposal and test matrix. Claude must remain advisory; apply edits and run tests in Codex only after reviewing the result.
```
