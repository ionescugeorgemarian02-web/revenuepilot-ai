#!/bin/sh
# Generează bundle.txt reproductibil din HEAD curent (nu se comite; se înregistrează SHA-256).
set -eu
out="${1:?cale ieșire}"
: > "$out"
for f in src/revenuepilot/*.py tests/*.py docs/security/threat-register.md docs/security/access-policies.md DECISIONS.md; do
  printf '\n===== FILE: %s =====\n' "$f" >> "$out"; cat "$f" >> "$out"
done
sha256sum "$out"
