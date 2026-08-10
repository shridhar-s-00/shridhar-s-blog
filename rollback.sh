#!/bin/sh
# ─────────────────────────────────────────────────────────────
# Roll back the "deferred-changes" batch and return to the exact
# version you had before it (main, commit 1c47bcd).
#
# Run it from the project folder:   sh rollback.sh
#
# This file is NOT tracked by git, so it won't be committed or pushed.
# Delete it whenever you like.
# ─────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo "Rolling back to your pre-change version (main)…"
git checkout main
./build

echo
echo "Done — you're back on main ($(git rev-parse --short HEAD)), dist/ rebuilt."
echo
echo "The new work is safe on the 'deferred-changes' branch. You can:"
echo "  • bring it back later:      git checkout deferred-changes"
echo "  • delete it permanently:    git branch -D deferred-changes"
