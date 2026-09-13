#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(id -u)" -ne 0 ]; then
  echo 'Run this bootstrap as root inside the dedicated Fleet VM.' >&2
  exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  build-essential pkg-config git ca-certificates curl \
  libx11-dev libxi-dev libxtst-dev libxext-dev libwayland-dev libxkbcommon-dev \
  python3-gi gir1.2-webkit2-4.1 gir1.2-gtk-3.0 python3-pip python3-venv xdotool
python3 -m venv --system-site-packages .venv-qwen
.venv-qwen/bin/python -m pip install --disable-pip-version-check \
  'cua-bench==0.2.11' cua-bench-ui pywebview 'pillow==11.3.0'
export CARGO_HOME=/opt/gameworld-cargo RUSTUP_HOME=/opt/gameworld-rustup
export PATH="$CARGO_HOME/bin:$PATH"
TOOLCHAIN=$(sed -n 's/^channel = "\(.*\)"/\1/p' cua-driver/rust/rust-toolchain.toml)
if [ ! -x "$CARGO_HOME/bin/rustup" ]; then
  curl -fsSL https://sh.rustup.rs -o /tmp/gameworld-rustup.sh
  sh /tmp/gameworld-rustup.sh -y --no-modify-path --default-toolchain "$TOOLCHAIN" --profile minimal
fi
rustup toolchain install "$TOOLCHAIN" --profile minimal
export CARGO_TARGET_DIR=/opt/gameworld-target
export CARGO_BUILD_JOBS=2 CARGO_PROFILE_RELEASE_DEBUG=0 CARGO_PROFILE_RELEASE_STRIP=true CARGO_INCREMENTAL=0
(cd cua-driver/rust && cargo build --locked --release -p cua-driver)
"$CARGO_TARGET_DIR/release/cua-driver" --version
.venv-qwen/bin/python -c 'import bench_ui, cua_bench; from PIL import ImageGrab; print("Python dependencies ready")'
echo QWEN_WORKER_BOOTSTRAP_OK
