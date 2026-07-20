#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TMP_BASE="${TMPDIR:-${TMP:-${TEMP:-.}}}"
TMP_ROOT="$(mktemp -d "$TMP_BASE/claude-agmsg-install.XXXXXX")"
TMP_ROOT="$(cd "$TMP_ROOT" && pwd -P)"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() {
  echo "test_install: $*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  case "$haystack" in
    *"$needle"*) ;;
    *) fail "expected output to contain: $needle" ;;
  esac
}

count_named_skills() {
  local codex_home="$1"
  local count=0
  local skill
  for skill in "$codex_home"/skills/*/SKILL.md; do
    [ -f "$skill" ] || continue
    if awk '
      NR == 1 && $0 == "---" { frontmatter = 1; next }
      frontmatter && $0 == "---" { exit }
      frontmatter && $0 ~ /^[[:space:]]*name[[:space:]]*:[[:space:]]*claude-agmsg-delegate[[:space:]]*$/ {
        found = 1
      }
      END { exit found ? 0 : 1 }
    ' "$skill"; then
      count=$((count + 1))
    fi
  done
  printf '%s\n' "$count"
}

fresh_home="$TMP_ROOT/fresh"
fresh_output="$("$ROOT/install.sh" --codex-home "$fresh_home")"
assert_contains "$fresh_output" "installed:"
assert_contains "$fresh_output" "restart Codex and start a new task"
[ "$(cat "$fresh_home/skills/claude-agmsg-delegate/VERSION")" = "$(cat "$ROOT/VERSION")" ] ||
  fail "fresh install version mismatch"
[ "$(count_named_skills "$fresh_home")" = "1" ] || fail "fresh install exposed duplicate Skills"

touch "$fresh_home/skills/claude-agmsg-delegate/preserve-me"
set +e
no_force_output="$("$ROOT/install.sh" --codex-home "$fresh_home" 2>&1)"
no_force_status=$?
set -e
[ "$no_force_status" -eq 3 ] || fail "reinstall without --force should exit 3"
assert_contains "$no_force_output" "rerun with --force"
[ -f "$fresh_home/skills/claude-agmsg-delegate/preserve-me" ] ||
  fail "reinstall without --force changed the existing install"

legacy="$fresh_home/skills/claude-agmsg-delegate.backup-20260101T000000Z"
mkdir -p "$legacy"
printf '%s\n' '---' 'name: claude-agmsg-delegate' '---' > "$legacy/SKILL.md"
printf '%s\n' '0.1.0' > "$legacy/VERSION"
printf '%s\n' 'legacy-sentinel' > "$legacy/sentinel.txt"

backup_root="$fresh_home/skill-backups/claude-agmsg-delegate"
mkdir -p "$backup_root/legacy-20260101T000000Z"
printf '%s\n' 'collision-sentinel' > "$backup_root/legacy-20260101T000000Z/sentinel.txt"

dry_output="$("$ROOT/install.sh" --codex-home "$fresh_home" --dry-run --force)"
assert_contains "$dry_output" "migrate old Skill backup"
assert_contains "$dry_output" "legacy-20260101T000000Z-2"
[ -d "$legacy" ] || fail "dry-run moved a legacy backup"

update_output="$("$ROOT/install.sh" --codex-home "$fresh_home" --force)"
assert_contains "$update_output" "migrated old Skill backup"
[ ! -e "$legacy" ] || fail "legacy backup remained inside skills/"
[ "$(cat "$backup_root/legacy-20260101T000000Z-2/sentinel.txt")" = "legacy-sentinel" ] ||
  fail "legacy backup content was not preserved"
[ "$(cat "$backup_root/legacy-20260101T000000Z/sentinel.txt")" = "collision-sentinel" ] ||
  fail "existing backup collision was overwritten"
[ "$(count_named_skills "$fresh_home")" = "1" ] ||
  fail "updated install exposed duplicate Skills"
[ -f "$backup_root"/*/preserve-me ] ||
  fail "the previous live install was not preserved outside skills/"

duplicate_home="$TMP_ROOT/duplicate"
"$ROOT/install.sh" --codex-home "$duplicate_home" >/dev/null
manual_duplicate="$duplicate_home/skills/manual-copy"
mkdir -p "$manual_duplicate"
printf '%s\n' '---' 'name: claude-agmsg-delegate' '---' > "$manual_duplicate/SKILL.md"
printf '%s\n' '0.1.0' > "$manual_duplicate/VERSION"
printf '%s\n' 'do-not-move' > "$manual_duplicate/sentinel.txt"

set +e
duplicate_output="$("$ROOT/install.sh" --codex-home "$duplicate_home" --force 2>&1)"
duplicate_status=$?
set -e
[ "$duplicate_status" -eq 4 ] || fail "unrelated duplicate should exit 4"
assert_contains "$duplicate_output" "duplicate Skill name detected"
assert_contains "$duplicate_output" "$manual_duplicate"
[ "$(cat "$manual_duplicate/sentinel.txt")" = "do-not-move" ] ||
  fail "installer moved an unrelated duplicate Skill"

echo "test_install: all installer scenarios passed"
