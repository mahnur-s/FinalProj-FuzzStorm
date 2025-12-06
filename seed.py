#!/usr/bin/env python3
"""Generate AFL++ seed inputs by piping queue entries through ./encoder."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
QUEUE_DIR = ROOT / "out2" / "default" / "queue"
OUTPUT_DIR = ROOT / "inspecial"
ENCODER_BIN = ROOT / "encoder"


def run_encoder(payload: bytes) -> list[str]:
    """Run the encoder binary and return its stdout split into lines."""
    proc = subprocess.run(
        [str(ENCODER_BIN)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"[WARN] encoder failed (code {proc.returncode})\n")
        if proc.stderr:
            sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))
        return []
    return proc.stdout.decode("utf-8", errors="replace").splitlines()


def main() -> None:
    if not QUEUE_DIR.is_dir():
        sys.exit(f"Queue directory not found: {QUEUE_DIR}")
    if not ENCODER_BIN.is_file():
        sys.exit(f"Encoder binary not found: {ENCODER_BIN}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    total_written = 0
    file_written = 0
    for path in sorted(QUEUE_DIR.iterdir()):
        if not path.is_file():
            continue

        payload = path.read_bytes()
        outputs = run_encoder(payload)
        if not outputs:
            continue

        fname = path.name.replace(":", "_")
        out_path = OUTPUT_DIR / fname
        out_path.write_text("\n".join(outputs) + "\n", encoding="utf-8")
        total_written += len(outputs)
        file_written += 1

    if file_written:
        print(
            f"Wrote {total_written} entries into {file_written} files under {OUTPUT_DIR}"
        )
    else:
        print("No output produced; nothing written.")


if __name__ == "__main__":
    main()
