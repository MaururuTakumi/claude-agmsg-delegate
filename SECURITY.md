# Security Policy

## Supported versions

The latest release and the current `main` branch receive security fixes.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting when available. Do not open a public issue containing credentials, private messages, paths with personal data, or exploitable details.

## Security boundaries

This project intentionally:

- runs delegated Claude with no tools;
- avoids permission bypasses;
- rejects common secret patterns before send;
- validates routing identifiers before older agmsg scripts receive them;
- uses agmsg scripts instead of direct database access;
- stores job state in a user-local permission-restricted cache;
- caps the default Claude budget per invocation.

Users remain responsible for reviewing delegated prompts and outputs and for protecting their local Codex, Claude Code, and agmsg installations.
