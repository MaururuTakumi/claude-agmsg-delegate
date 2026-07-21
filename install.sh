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
  --force            Move an existing install to a backup outside skills/.
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
BACKUP_ROOT="$CODEX_HOME_VALUE/skill-backups/claude-agmsg-delegate"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

for file in SKILL.md README.md LICENSE VERSION scripts/delegate_claude.py; do
  [ -f "$ROOT/$file" ] || { echo "install: missing source file: $file" >&2; exit 1; }
done

python3 -m py_compile "$ROOT/scripts/delegate_claude.py"

path_exists() {
  [ -e "$1" ] || [ -L "$1" ]
}

next_available_path() {
  local base="$1"
  local candidate="$base"
  local suffix=2
  while path_exists "$candidate"; do
    candidate="$base-$suffix"
    suffix=$((suffix + 1))
  done
  printf '%s\n' "$candidate"
}

skill_version() {
  local directory="$1"
  if [ -f "$directory/VERSION" ]; then
    tr -d '[:space:]' < "$directory/VERSION"
  else
    printf 'unknown\n'
  fi
}

migrate_old_layout_backups() {
  local mode="$1"
  local legacy legacy_name legacy_suffix target version
  for legacy in "$DEST".backup-*; do
    path_exists "$legacy" || continue
    if [ -L "$legacy" ] || [ ! -d "$legacy" ]; then
      echo "install: warning: not moving non-directory legacy backup: $legacy" >&2
      continue
    fi
    legacy_name="$(basename "$legacy")"
    legacy_suffix="${legacy_name#claude-agmsg-delegate.backup-}"
    target="$(next_available_path "$BACKUP_ROOT/legacy-$legacy_suffix")"
    version="$(skill_version "$legacy")"
    if [ "$mode" = "dry-run" ]; then
      echo "dry-run: migrate old Skill backup $legacy -> $target (version $version)"
    else
      mv "$legacy" "$target"
      echo "install: migrated old Skill backup $legacy -> $target (version $version)"
    fi
  done
}

find_named_skills() {
  python3 - "$CODEX_HOME_VALUE/skills" <<'PY'
from pathlib import Path
import sys

skills_root = Path(sys.argv[1])
if not skills_root.is_dir():
    raise SystemExit(0)

for directory in sorted(skills_root.iterdir()):
    skill = directory / "SKILL.md"
    if not skill.is_file():
        continue
    try:
        lines = skill.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        continue
    if not lines or lines[0].strip() != "---":
        continue
    name = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            name = value.strip().strip("\"'")
            break
    if name != "claude-agmsg-delegate":
        continue
    version_path = directory / "VERSION"
    try:
        version = version_path.read_text(encoding="utf-8").strip() or "unknown"
    except (OSError, UnicodeError):
        version = "unknown"
    print(f"{directory}\t{version}")
PY
}

if [ "$DRY_RUN" -eq 1 ]; then
  echo "dry-run: source=$ROOT"
  echo "dry-run: destination=$DEST"
  if path_exists "$DEST"; then
    if [ "$FORCE" -eq 1 ]; then
      migrate_old_layout_backups dry-run
      BACKUP="$(next_available_path "$BACKUP_ROOT/$STAMP")"
      echo "dry-run: move existing install to $BACKUP (version $(skill_version "$DEST"))"
    else
      echo "dry-run: destination exists; rerun with --force to back it up outside skills/ and install" >&2
      exit 3
    fi
  else
    migrate_old_layout_backups dry-run
  fi
  echo "dry-run: copy SKILL.md README.md LICENSE VERSION scripts/ tests/"
  echo "dry-run: installer runs no Claude model, makes no agmsg change, and sends no network request"
  exit 0
fi

mkdir -p "$(dirname "$DEST")"
if path_exists "$DEST"; then
  if [ "$FORCE" -ne 1 ]; then
    echo "install: destination exists: $DEST" >&2
    echo "install: rerun with --force to preserve it outside skills/" >&2
    exit 3
  fi
fi

mkdir -p "$BACKUP_ROOT" || {
  echo "install: cannot create backup root: $BACKUP_ROOT" >&2
  exit 1
}
[ -d "$BACKUP_ROOT" ] && [ -w "$BACKUP_ROOT" ] || {
  echo "install: backup root is not a writable directory: $BACKUP_ROOT" >&2
  exit 1
}

migrate_old_layout_backups install

if path_exists "$DEST"; then
  BACKUP="$(next_available_path "$BACKUP_ROOT/$STAMP")"
  PREVIOUS_VERSION="$(skill_version "$DEST")"
  mv "$DEST" "$BACKUP"
  echo "install: previous install moved to $BACKUP (version $PREVIOUS_VERSION)"
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

NAMED_SKILLS="$(find_named_skills)"
NAMED_SKILL_COUNT="$(printf '%s\n' "$NAMED_SKILLS" | awk 'NF { count++ } END { print count + 0 }')"
if [ "$NAMED_SKILL_COUNT" -ne 1 ]; then
  echo "install: duplicate Skill name detected; Codex may load a stale claude-agmsg-delegate" >&2
  printf '%s\n' "$NAMED_SKILLS" | while IFS="$(printf '\t')" read -r path version; do
    [ -n "$path" ] || continue
    echo "install: duplicate: $path (version $version)" >&2
  done
  echo "install: move unrelated duplicate Skills outside $CODEX_HOME_VALUE/skills, then rerun the installer" >&2
  exit 4
fi

echo "installed: $DEST (version $INSTALLED_VERSION)"
echo "backup root: $BACKUP_ROOT"
echo "doctor: change to the target project, then run python3 $DEST/scripts/delegate_claude.py doctor"
echo "next: restart Codex and start a new task, then ask it to use \$claude-agmsg-delegate"
echo "note: the current task may keep the pre-update Skill instructions until a new task starts"
echo "verify: python3 $DEST/scripts/delegate_claude.py run --model fable --task 'Installation verification only.' --dry-run"
