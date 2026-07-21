Run make test and ./install.sh --dry-run, then run ./install.sh to install the offline Skill before agmsg or any other runtime dependency is repaired. Python
3.9.6 is supported because the requirement is Python 3.9+.

From the real target project, run delegate_claude.py doctor. Doctor does not change settings, send agmsg, invoke a model, create job state, or use the
network. It discovers a standard out-of-PATH Claude install and reports
CLAUDE_BIN_OUTSIDE_PATH, then pins that absolute path. The missing api.sh in
agmsg 1.1.7 reports AGMSG_OUTDATED; official agmsg 1.1.8 and newer includes it.

Stop and obtain explicit approval before npx agmsg, team join, or delivery
selection. Installation and doctor use no model, and delegation has no API fallback: only the verified paid Claude.ai subscription route is accepted.
