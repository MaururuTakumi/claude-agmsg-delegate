#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CODEX_HOME_VALUE="${CODEX_HOME:-$HOME/.codex}"
DRY_RUN=0
FORCE=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [--dry-run] [--force] [--codex-home PATH]

Installs the Skill into <codex-home>/skills/claude-agmsg-delegate.

  --dry-run          Print actions without writing.
  --force            Move an existing install to a timestamped backup.
  --codex-home PATH  Override CODEX_HOME for this install.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    --codex-home)
      shift
      [ "$#" -gt 0 ] || { echo "install: --codex-home needs a path" >&2; exit 2; }
      CODEX_HOME_VALUE="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "install: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

DEST="$CODEX_HOME_VALUE/skills/claude-agmsg-delegate"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$DEST.backup-$STAMP"

for file in SKILL.md README.md LICENSE VERSION scripts/delegate_claude.py; do
  [ -f "$ROOT/$file" ] || { echo "install: missing source file: $file" >&2; exit 1; }
done

python3 -m py_compile "$ROOT/scripts/delegate_claude.py"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "dry-run: source=$ROOT"
  echo "dry-run: destination=$DEST"
  if [ -e "$DEST" ]; then
    if [ "$FORCE" -eq 1 ]; then
      echo "dry-run: move existing install to $BACKUP"
    else
      echo "dry-run: destination exists; rerun with --force to back it up and install" >&2
      exit 3
    fi
  fi
  echo "dry-run: copy SKILL.md README.md LICENSE VERSION scripts/ tests/"
  echo "dry-run: installer runs no Claude model, makes no agmsg change, and sends no network request"
  exit 0
fi

mkdir -p "$(dirname "$DEST")"
if [ -e "$DEST" ]; then
  if [ "$FORCE" -ne 1 ]; then
    echo "install: destination exists: $DEST" >&2
    echo "install: rerun with --force to preserve it as a timestamped backup" >&2
    exit 3
  fi
  mv "$DEST" "$BACKUP"
  echo "install: previous install moved to $BACKUP"
fi

mkdir -p "$DEST/scripts" "$DEST/tests"
cp "$ROOT/SKILL.md" "$DEST/SKILL.md"
cp "$ROOT/README.md" "$DEST/README.md"
cp "$ROOT/LICENSE" "$DEST/LICENSE"
cp "$ROOT/VERSION" "$DEST/VERSION"
cp "$ROOT/scripts/delegate_claude.py" "$DEST/scripts/delegate_claude.py"
cp "$ROOT/tests/test_delegate_claude.py" "$DEST/tests/test_delegate_claude.py"
chmod +x "$DEST/scripts/delegate_claude.py" "$DEST/tests/test_delegate_claude.py"

python3 -m py_compile "$DEST/scripts/delegate_claude.py"
python3 "$DEST/scripts/delegate_claude.py" --help >/dev/null

INSTALLED_VERSION="$(python3 "$DEST/scripts/delegate_claude.py" --version)"
[ "$INSTALLED_VERSION" = "$(cat "$DEST/VERSION")" ] || {
  echo "install: installed version mismatch" >&2
  exit 1
}

echo "installed: $DEST (version $INSTALLED_VERSION)"
echo "next: restart Codex, then ask it to use \$claude-agmsg-delegate"
echo "verify: python3 $DEST/scripts/delegate_claude.py run --model fable --task 'Installation verification only.' --dry-run"
