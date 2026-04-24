"""Status pane viewer: runs control-plane status in a managed terminal loop.

Clears the screen, runs the status command, disables any mouse modes that
Rich may have enabled, then waits for r (refresh) or q (quit).  The restart
loop in the launcher brings the viewer back when it exits.

Usage: python3 -m fob.status_viewer <cp-script> [extra args...]
"""
from __future__ import annotations
import os
import subprocess
import sys
import termios
import tty


_MOUSE_OFF = "\033[?1000l\033[?1002l\033[?1003l\033[?1015l\033[?1006l"
_HELP = "  r = refresh   q = quit"


def _getch() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python3 -m fob.status_viewer <cp-script> [args...]")
        sys.exit(1)

    cp_script = sys.argv[1]
    extra = sys.argv[2:]

    while True:
        os.system("clear")
        subprocess.run([cp_script, "status"] + extra)
        sys.stdout.write(_MOUSE_OFF + "\n" + _HELP + "\n")
        sys.stdout.flush()
        key = _getch()
        if key in ("q", "Q", "\x1b"):
            break


if __name__ == "__main__":
    main()
