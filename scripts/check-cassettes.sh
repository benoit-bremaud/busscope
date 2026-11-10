#!/bin/sh
# Filter for recorded third-party cassettes (D2, `just record`): run before committing them.
# Fails when gitleaks finds a secret, or when a cassette keeps a credential header or a personal
# email address (example.com/.org/.net, their subdomains and noreply addresses are allowed
# placeholders). Only file names are printed, never the matched value. Needs gitleaks, grep.
#   check-cassettes.sh <dir>
set -eu
dir=${1:?usage: check-cassettes.sh <dir>}
[ -d "$dir" ] || { echo "check-cassettes: no directory $dir" >&2; exit 1; }
rc=0
gitleaks dir --redact --no-banner "$dir" || rc=1
hdr='(authorization|proxy-authorization|cookie|set-cookie|x-api-key|api-key|x-auth-token)'
# a header as a key ("Authorization": …) or as a HAR-style record ({"name": "Authorization", …})
if grep -rliE "\"?$hdr\"?[[:space:]]*[:=]|\"name\"[[:space:]]*:[[:space:]]*\"$hdr\"" "$dir"; then
  echo "check-cassettes: credential header kept in the files above, filter it out of the recording" >&2; rc=1
fi
if grep -rhoE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$dir" | grep -viE '@([a-z0-9-]+\.)*example\.(com|org|net)$|noreply' > /dev/null; then
  grep -rlE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$dir"
  echo "check-cassettes: personal email address kept in the files above, replace it with an example.com placeholder" >&2; rc=1
fi
[ "$rc" -eq 0 ] && echo "check-cassettes: $dir clean"
exit "$rc"
