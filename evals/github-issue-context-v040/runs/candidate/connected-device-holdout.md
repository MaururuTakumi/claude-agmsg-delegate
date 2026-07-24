Keep the delegated worker read-only and use the supported narrow entry:

`delegate_claude.py run --model fable --github-issue owner/repo#123 --confirm-github-issue-context-safe --task "Review this Issue."`

The wrapper calls the device's authenticated `gh issue view` for that exact
reference and supplies the bounded result as untrusted context. It does not
restore the normal Claude settings or expose general shell access to Fable.
