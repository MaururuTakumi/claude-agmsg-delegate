Version 0.3.0 does not require list-ids.sh. Run the repository tests, then use
`./install.sh --dry-run --force` followed by `./install.sh --force`. The installer moves its old `claude-agmsg-delegate.backup-*` directories outside the Skill discovery tree into `~/.codex/skill-backups/claude-agmsg-delegate/`
and preserves every backup intact without deleting or overwriting it.

If an unrelated directory still declares the same Skill name, the installer
lists its path and version and stops with status 4 rather than moving or
deleting user data. Move only the unwanted copy outside `skills/`, rerun the
installer, confirm `delegate_claude.py --version` is 0.3.0, then restart Codex
and open a new task because the current task may retain pre-update instructions.
Do not change agmsg. The subscription-only policy remains unchanged.
