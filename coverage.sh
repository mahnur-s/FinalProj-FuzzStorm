#!/usr/bin/env bash
set -euo pipefail

#############################
# Config
#############################

# Project root (this script's directory)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Paths
JSONCPP_DIR="$ROOT/jsoncpp"
COV_BUILD_DIR="$JSONCPP_DIR/build-llvmcov"

HARNESS_SRC="$ROOT/main.cpp"            # your harness source
HARNESS_BIN="$ROOT/jsoncpp_fuzz_cov"    # coverage build of harness

AFL_OUT_DIR="$ROOT/out3/default"         # AFL++ -o out  => out/default/...
QUEUE_DIR="$AFL_OUT_DIR/queue"

PROFRAW_DIR="$ROOT/profraw"
PROFDATA_FILE="$ROOT/coverage.profdata"
COV_HTML_DIR="$ROOT/coverage_html"

# Compilers / flags
C_COMPILER=clang
CXX_COMPILER=clang++

COV_FLAGS="-O0 -g -fprofile-instr-generate -fcoverage-mapping"

#############################
# 1) Build jsoncpp with coverage
#############################

echo "[*] Building jsoncpp with LLVM coverage..."

mkdir -p "$COV_BUILD_DIR"
cd "$COV_BUILD_DIR"

cmake .. \
  -DCMAKE_C_COMPILER="$C_COMPILER" \
  -DCMAKE_CXX_COMPILER="$CXX_COMPILER" \
  -DCMAKE_C_FLAGS="$COV_FLAGS" \
  -DCMAKE_CXX_FLAGS="$COV_FLAGS"

cmake --build . -j"$(nproc)"

# Try to guess the static library path.
# If this fails, run:  find "$COV_BUILD_DIR" -name 'libjsoncpp*.a'
JSONCPP_LIB="/home/ahmad/introtonetwork/csproj/jsoncpp/build-llvmcov/lib/libjsoncpp.a"
if [[ ! -f "$JSONCPP_LIB" ]]; then
  echo "[!] Could not find libjsoncpp.a at:"
  echo "    $JSONCPP_LIB"
  echo "    Run:  find \"$COV_BUILD_DIR\" -name 'libjsoncpp*.a'"
  echo "    Then update JSONCPP_LIB in coverage.sh accordingly."
  exit 1
fi

echo "[+] Using jsoncpp library: $JSONCPP_LIB"

#############################
# 2) Build coverage harness
#############################

echo "[*] Building coverage harness: $HARNESS_BIN"

cd "$ROOT"

$CXX_COMPILER $COV_FLAGS \
  -I"$JSONCPP_DIR/include" \
  "$HARNESS_SRC" "$JSONCPP_LIB" \
  -o "$HARNESS_BIN"

echo "[+] Built $HARNESS_BIN"

#############################
# 3) Replay AFL++ corpus (stdin harness)
#############################

if [[ ! -d "$QUEUE_DIR" ]]; then
  echo "[!] AFL++ queue directory not found:"
  echo "    $QUEUE_DIR"
  echo "    Make sure you fuzzed with: afl-fuzz -i in -o out -- ./jsoncpp_fuzz"
  exit 1
fi

echo "[*] Replaying AFL++ corpus from: $QUEUE_DIR"

rm -rf "$PROFRAW_DIR"
mkdir -p "$PROFRAW_DIR"

shopt -s nullglob
inputs=( "$QUEUE_DIR"/id:* )

if (( ${#inputs[@]} == 0 )); then
  echo "[!] No inputs found in $QUEUE_DIR"
  exit 1
fi

# Harness reads from stdin and can process multiple inputs per run,
# but here we just feed one input per run via stdin and let it exit on EOF.
for f in "${inputs[@]}"; do
  echo "    -> $f"
  LLVM_PROFILE_FILE="$PROFRAW_DIR/%p.profraw" \
    "$HARNESS_BIN" < "$f" >/dev/null 2>&1 || true
done

echo "[+] Collected raw profiles in $PROFRAW_DIR"

#############################
# 4) Merge & report coverage
#############################

echo "[*] Merging profiles with llvm-profdata..."

llvm-profdata merge -o "$PROFDATA_FILE" "$PROFRAW_DIR"/*.profraw

echo "[*] llvm-cov report (summary):"
echo "=============================================="
llvm-cov report "$HARNESS_BIN" -instr-profile="$PROFDATA_FILE"
echo "=============================================="

echo "[*] Generating HTML report in: $COV_HTML_DIR"

rm -rf "$COV_HTML_DIR"
llvm-cov show "$HARNESS_BIN" \
  -instr-profile="$PROFDATA_FILE" \
  -format=html \
  -output-dir="$COV_HTML_DIR" \
  -ignore-filename-regex='/usr/include'

echo
echo "[+] Done."
echo "    Text summary printed above."
echo "    Open this in your browser for line/branch coverage:"
echo "        $COV_HTML_DIR/index.html"
