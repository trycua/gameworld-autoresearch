#!/usr/bin/env bash
set -euo pipefail
cd "${CUA_DRIVER_SRC:-/opt/gameworld-autoresearch/cua-driver}/rust"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/opt/gameworld-target}"
export CARGO_INCREMENTAL=1
cargo build --offline --locked --release -p cua-driver
install -m755 "$CARGO_TARGET_DIR/release/cua-driver" /usr/local/bin/cua-driver.next
mv -f /usr/local/bin/cua-driver.next /usr/local/bin/cua-driver
/usr/local/bin/cua-driver --version
