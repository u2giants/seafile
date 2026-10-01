#!/bin/sh
# drive-nudge.sh — make Synology Drive / ShareSync see files written by the
# seaf-cli container on edgesynology1.
#
# Why: Drive learns about changes from synotifyd, which watches the HOST mount
# of each share. Writes made inside a container go through Docker's bind-mount
# copy of that mount, so Drive never hears about them and ShareSync never sends
# them to edgesynology2 (2026-10-01: 1,646 items missed since 2026-09-17).
# Proven: the same write from the host syncs; from inside the container (as root
# or uid 1000) it does not. A host-side rename-and-back of the item makes Drive
# register it (with its parent directories). A no-op chmod also works but strips
# Synology ACLs, and a same-mtime touch is ignored, so rename-and-back it is.
#
# What: every run finds items under the seaf-cli library roots whose ctime is
# newer than the last run and that are owned by root (seaf-cli writes as root),
# and renames each FILE (and each EMPTY directory) to a temporary sibling name
# and straight back, from the host. Content, owner, ACL, mode and mtime are
# unchanged. Non-empty directories are never renamed (their files carry them),
# so a parent's ctime change cannot cascade. Items nudged by the previous run
# are skipped so the nudge's own ctime change does not loop.
#
# Runs as root from DSM Task Scheduler ("seaf-cli Drive nudge", every 15 min).
# Source of truth: u2giants/seafile synology-seaf-cli/drive-nudge.sh.
set -u
STATE=/volume1/docker/seaf-cli/drive-nudge
ROOTS="/volume1/mac/Decor/Character Licensed
/volume1/mac/Decor/Generic Decor
/volume1/mac/Art Library
/volume1/styleguides
/volume1/files/shared"

mkdir -p "$STATE"
exec 9>"$STATE/lock"
flock -n 9 || exit 0

[ -f "$STATE/stamp" ] || touch -d '-1 day' "$STATE/stamp"
touch "$STATE/stamp.next"
: > "$STATE/found"
: >> "$STATE/last"

echo "$ROOTS" | while IFS= read -r root; do
  [ -d "$root" ] || continue
  nice -n 19 find "$root" \
    \( -name '@eaDir' -o -name '#recycle' -o -name '#snapshot' -o -name '.SynologyWorkingDirectory' \) -prune \
    -o -user root -cnewer "$STATE/stamp" -print 2>/dev/null
done | grep -v -x -F -f "$STATE/last" > "$STATE/found"

n=0
while IFS= read -r p; do
  if [ -f "$p" ] || [ -L "$p" ]; then :
  elif [ -d "$p" ] && [ -z "$(ls -A "$p" 2>/dev/null)" ]; then :
  else continue; fi
  t="$p.drive-nudge.$$"
  [ -e "$t" ] && continue
  if mv -T -- "$p" "$t" 2>/dev/null; then
    if mv -T -- "$t" "$p"; then n=$((n+1)); else echo "$(date '+%F %T') FAILED to restore $t" >> "$STATE/log"; fi
  fi
done < "$STATE/found"

mv "$STATE/found" "$STATE/last"
mv "$STATE/stamp.next" "$STATE/stamp"
echo "$(date '+%F %T %Z') nudged=$n" >> "$STATE/log"
tail -n 2000 "$STATE/log" > "$STATE/log.tmp" && mv "$STATE/log.tmp" "$STATE/log"
