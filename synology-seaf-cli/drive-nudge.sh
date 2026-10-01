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
# What: every run looks under the seaf-cli library roots for items whose ctime
# is newer than the last run and renames each one to a temporary sibling name
# and straight back, from the host:
#   - root-owned FILES: new or changed by seaf-cli;
#   - DIRECTORIES of any owner below a library root (this also registers new
#     directories and their contents): a delete or rename made by
#     seaf-cli inside a directory only shows as that directory's ctime change,
#     and a host-side rename of the directory makes Drive re-read it, so the
#     delete/rename reaches edgesynology2 (proven 2026-10-01).
# Content, owner, ACL, mode and mtime are unchanged. The library roots and their
# ancestors are never renamed. After each run the ctime of every nudged item
# and of its parent is recorded; an item whose ctime still equals the recorded
# value is skipped next run, so the nudge's own ctime changes never cascade.
#
# Runs as root from DSM Task Scheduler ("seaf-cli Drive nudge", every 15 min).
# Source of truth: u2giants/seafile synology-seaf-cli/drive-nudge.sh.
set -u
STATE=${DRIVE_NUDGE_STATE:-/volume1/docker/seaf-cli/drive-nudge}
ROOTS=${DRIVE_NUDGE_ROOTS:-"/volume1/mac/Decor/Character Licensed
/volume1/mac/Decor/Generic Decor
/volume1/mac/Art Library
/volume1/styleguides
/volume1/files/shared"}

mkdir -p "$STATE"
exec 9>"$STATE/lock"
flock -n 9 || exit 0

[ -f "$STATE/stamp" ] || touch -d '-1 day' "$STATE/stamp"
touch "$STATE/stamp.next"
touch "$STATE/seen"
: > "$STATE/found"
: > "$STATE/done"

echo "$ROOTS" | while IFS= read -r root; do
  [ -d "$root" ] || continue
  nice -n 19 find "$root" -mindepth 1 \
    \( -name '@eaDir' -o -name '#recycle' -o -name '#snapshot' -o -name '.SynologyWorkingDirectory' \) -prune \
    -o -cnewer "$STATE/stamp" \( -type d -o -user root \) -print 2>/dev/null
done > "$STATE/found"

# ctime with nanoseconds (stat %Z is whole seconds only on this coreutils)
ct() { find "$1" -maxdepth 0 -printf '%C@' 2>/dev/null; }

n=0
nudge() {
  t="$1.drive-nudge.$$"
  [ -e "$t" ] && return 1
  mv -T -- "$1" "$t" 2>/dev/null || return 1
  if mv -T -- "$t" "$1"; then
    printf '%s\n%s\n' "$1" "$(dirname -- "$1")" >> "$STATE/done"
    n=$((n+1))
  else
    echo "$(date '+%F %T') FAILED to restore $t" >> "$STATE/log"
  fi
}

# Files first, then directories (a directory rename re-reads its subtree).
for pass in files dirs; do
  while IFS= read -r p; do
    [ -e "$p" ] || [ -L "$p" ] || continue
    if grep -q -x -F -- "$(ct "$p")	$p" "$STATE/seen"; then continue; fi
    if [ -d "$p" ] && [ ! -L "$p" ]; then
      [ "$pass" = dirs ] && nudge "$p"
    else
      [ "$pass" = files ] && [ "$(stat -c %U -- "$p")" = root ] && nudge "$p"
    fi
  done < "$STATE/found"
done

sort -u "$STATE/done" | while IFS= read -r p; do
  [ -e "$p" ] && printf '%s\t%s\n' "$(ct "$p")" "$p"
done > "$STATE/seen.new"
mv "$STATE/seen.new" "$STATE/seen"
mv "$STATE/stamp.next" "$STATE/stamp"
echo "$(date '+%F %T %Z') candidates=$(wc -l < "$STATE/found") nudged=$n" >> "$STATE/log"
tail -n 2000 "$STATE/log" > "$STATE/log.tmp" && mv "$STATE/log.tmp" "$STATE/log"
