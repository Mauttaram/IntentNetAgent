"""
Record the IntentNetAgent demo via a real PTY so timing is accurate.

asciinema's headless mode buffers all output when stdout is a pipe — all events
collapse to t=0. This script allocates a genuine PTY so the subprocess thinks
it has a real terminal: stdout is unbuffered, output arrives in real-time, and
timestamps in the cast file are correct.

Outputs:
  demo/demo.cast   — asciinema v2 cast (play with: asciinema play demo.cast)
  demo/demo.gif    — animated GIF for slides (generated via agg)
"""
from __future__ import annotations

import fcntl
import json
import os
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE       = Path(__file__).resolve().parent          # IntentNetAgent/demo/
PKG_ROOT   = HERE.parent                              # IntentNetAgent/
VENV_PY    = PKG_ROOT.parent / "ScalableAgents" / ".venv" / "bin" / "python"
CAST_FILE  = HERE / "demo.cast"
GIF_FILE   = HERE / "demo.gif"

COLS, ROWS = 120, 40
TITLE      = "IntentNetAgent — Intent-Based Networking for SMBs"


# ---------------------------------------------------------------------------
# PTY recorder
# ---------------------------------------------------------------------------
def record() -> None:
    print(f"Recording demo via PTY …")
    print(f"  Python:  {VENV_PY}")
    print(f"  Output:  {CAST_FILE}\n")

    master_fd, slave_fd = os.openpty()

    # Set terminal dimensions on the slave end
    winsize = struct.pack("HHHH", ROWS, COLS, 0, 0)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    env = {
        **os.environ,
        "PYTHONPATH":        str(PKG_ROOT),
        "PYTHONUNBUFFERED":  "1",
        "TERM":              "xterm-256color",
        "COLUMNS":           str(COLS),
        "LINES":             str(ROWS),
    }

    proc = subprocess.Popen(
        [str(VENV_PY), "-u", "-m", "intent_net_agent.demo"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=subprocess.DEVNULL,
        env=env,
        close_fds=True,
    )
    os.close(slave_fd)   # parent no longer needs slave end

    header = {
        "version": 2,
        "width":   COLS,
        "height":  ROWS,
        "title":   TITLE,
        "env":     {"TERM": "xterm-256color"},
    }
    events: list[list] = []
    start = time.time()

    # Read from the master end until the subprocess exits
    while True:
        try:
            readable, _, _ = select.select([master_fd], [], [], 0.05)
        except (ValueError, OSError):
            break

        if readable:
            try:
                data = os.read(master_fd, 4096)
            except OSError:
                break
            if data:
                ts = round(time.time() - start, 6)
                events.append([ts, "o", data.decode("utf-8", errors="replace")])

        if proc.poll() is not None:
            # Drain any remaining bytes
            while True:
                try:
                    r, _, _ = select.select([master_fd], [], [], 0.05)
                    if not r:
                        break
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    ts = round(time.time() - start, 6)
                    events.append([ts, "o", data.decode("utf-8", errors="replace")])
                except OSError:
                    break
            break

    os.close(master_fd)
    proc.wait()

    duration = events[-1][0] if events else 0.0
    print(f"\nCaptured {len(events)} events over {duration:.1f}s")

    # Write cast file
    with open(CAST_FILE, "w") as f:
        f.write(json.dumps(header) + "\n")
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    print(f"Cast saved → {CAST_FILE}")


# ---------------------------------------------------------------------------
# GIF conversion via agg
# ---------------------------------------------------------------------------
def convert_to_gif() -> None:
    agg = "agg"
    print(f"\nConverting to GIF …")
    result = subprocess.run(
        [
            agg,
            "--cols",      str(COLS),
            "--rows",      str(ROWS),
            "--font-size", "14",
            "--speed",     "1.0",
            "--no-loop",
            str(CAST_FILE),
            str(GIF_FILE),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"agg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_mb = GIF_FILE.stat().st_size / 1_000_000
    print(f"GIF saved  → {GIF_FILE}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    record()
    convert_to_gif()
    print("\nDone. Files ready for the hackathon presentation:")
    print(f"  {CAST_FILE}  ← play with: asciinema play demo/demo.cast")
    print(f"  {GIF_FILE}   ← drop into slides as an animated image")
