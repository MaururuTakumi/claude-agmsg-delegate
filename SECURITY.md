# Security Policy

## Supported versions

The latest release and the current `main` branch receive security fixes.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting when available. Do not open a public issue containing credentials, private messages, paths with personal data, or exploitable details.

## Security boundaries

This project intentionally:

- runs Fable and advisory Sonnet jobs with only `Read,Glob,Grep` in plan mode
  inside the target project directory;
- allows only explicit Sonnet implementer jobs to edit a Git workspace, using
  `Read,Edit,Write,Glob,Grep` with `--permission-mode acceptEdits` and a required
  Codex diff review;
- avoids permission bypasses;
- rejects common secret patterns before send;
- validates routing identifiers before older agmsg scripts receive them;
- uses agmsg scripts instead of direct database access;
- stores job state in a user-local permission-restricted cache;
- requires a paid Claude.ai `/login` OAuth session before send and rechecks it immediately before inference;
- rejects API keys, auth tokens, custom base URLs, API-key helpers, and Bedrock, Vertex, Foundry, or Mantle routes with no fallback;
- passes Claude a minimal environment allowlist and disables user, project, and local setting sources;
- optionally fetches only explicitly selected GitHub Issues through the
  authenticated `gh` CLI, outside Claude, without passing GitHub token
  environment variables or enabling Bash;
- requires explicit confirmation that Issue context contains no secrets,
  credentials, patient information, or unnecessary personal data, omits
  comment author identities, and rejects common secret patterns;
- rechecks authentication after inference and discards output if the route changed;
- runs headlessly without requiring a Claude UI, tmux session, daemon, or monitor.

agmsg carries task and result envelopes; it does not upload a repository.
During a real job, the local Claude Code process may send successful file-tool
results to Claude.ai under the verified subscription route. This is the same
service boundary as using terminal Claude Code on the project, with a narrower
tool and settings policy. An explicit workspace-review request authorizes one
bounded ordinary-file read, but never overrides named exclusions or the secret,
credential, private-key, and unnecessary-personal-data prohibitions.

Workspace-write mode does not expose Bash and does not authorize install,
deploy, push, or unrelated-path access. Users remain responsible for reviewing
delegated prompts, outputs, and actual Git diffs; running relevant tests;
protecting their local Codex, Claude Code, and agmsg installations; and keeping
Claude account-level Extra usage / usage credits disabled when zero variable
charges are required. Claude auth status proves the active credential route; it
does not expose that separate account setting.
