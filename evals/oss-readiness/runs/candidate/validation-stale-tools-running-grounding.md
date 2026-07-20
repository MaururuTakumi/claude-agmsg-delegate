Read,Glob,Grep is the expected advisory policy. The copied toolsなし rule is
stale 0.1 guidance, so do not switch Fable to tool-free or ask for a one-off
permission exception. Verify `delegate_claude.py --version` reports 0.2.1 and
the dry-run reports contract_version=2. If not, update, reinstall the Skill, and
restart Codex.

Do not resubmit the task. Inspect worker_stage and running_seconds, then use the
returned collect command with --wait 60 to collect the same job_id. A dead
worker is reported failed on collection. Dry-run proves only configuration; a
completed result proves project inspection only when workspace_grounded=true
and files_read contains relevant project-relative paths observed from Read tool
events.
