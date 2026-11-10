#!/bin/sh
# commit-msg check (#192): the subject line must follow Conventional Commits 1.0.0 with the types of
# agent-rules/core.md § Naming, at most 100 characters. Merge, revert and fixup/squash subjects pass.
# Usage: check-commit-msg.sh <commit-msg-file>   (lefthook commit-msg passes {1})
set -e

[ $# -eq 1 ] && [ -r "$1" ] || { echo "usage: check-commit-msg.sh <commit-msg-file>" >&2; exit 2; }
subject=$(grep -v '^#' "$1" | sed -n '/./{p;q;}')

case "$subject" in
  'Merge '*|'Revert "'*|'fixup! '*|'squash! '*|'amend! '*) exit 0 ;;
esac

types='feat|fix|docs|chore|refactor|test|ci|build|perf'
if ! printf '%s\n' "$subject" | grep -qE "^($types)(\([a-z0-9._/-]+\))?!?: [^ ](.*[^.])?$"; then
  echo "commit-msg: subject is not '<type>(<scope>): <subject>' (types: $types, no final period):" >&2
  echo "  $subject" >&2
  exit 1
fi
if [ "${#subject}" -gt 100 ]; then
  echo "commit-msg: subject is ${#subject} characters, 100 at most" >&2
  exit 1
fi
