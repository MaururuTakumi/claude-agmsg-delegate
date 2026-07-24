Use the explicit read-only Issue input:

`delegate_claude.py run --model fable --github-issue 42 --confirm-github-issue-context-safe --task "Review the requirements."`

The wrapper uses the authenticated `gh` CLI to read the selected Issue and
comments. Fable keeps only its local read-only file tools; no general shell or
GitHub write capability is enabled.
