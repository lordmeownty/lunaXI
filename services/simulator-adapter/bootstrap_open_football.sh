#!/usr/bin/env bash
# Clones and builds the exact Open Football revision reviewed for Luna XI (build-time only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="${OPEN_FOOTBALL_DIR:-$ROOT/third-party/open-football}"
REVISION="${OPEN_FOOTBALL_REVISION:-$(python -c "import json;print(json.load(open('$ROOT/services/simulator-adapter/integration.json'))['revision'])")}"
[[ -d "$TARGET/.git" ]] || git clone https://github.com/ZOXEXIVO/open-football "$TARGET"
git -C "$TARGET" fetch --depth 1 origin "$REVISION"
git -C "$TARGET" checkout --detach "$REVISION"
cargo build --manifest-path "$TARGET/Cargo.toml" --release
echo "Open Football built at $TARGET ($REVISION)"
