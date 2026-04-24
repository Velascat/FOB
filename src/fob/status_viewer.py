"""Status pane viewer: runs control-plane status in a managed terminal loop.

cp-status.py uses Rich console.clear() in a while-True/2s loop, which dumps
content to Zellij's scrollback on every cycle → infinite scroll.  Fix: run the
subprocess inside alternate screen so its output has no scrollback buffer.

On Ctrl+C the child (cp-status.py) receives SIGINT and exits; the parent
ignores it (preexec_fn restores SIG_DFL in the child so it works normally).
After the child exits we disable mouse modes and drop back to the main screen.

Usage: python3 -m fob.status_viewer <cp-script> [extra args...]
"""
from __future__ import annotations
import signal
import subprocess
import sys
import termios
import tty


_MOUSE_OFF = "\033[?1000l\033[?1002l\033[?1003l\033[?1015l\033[?1006l"
_ALT_ON    = "\033[?1049h"   # enter alternate screen (no scrollback)
_ALT_OFF   = "\033[?1049l"   # exit alternate screen
_HELP      = "  r = refresh   q = quit (Ctrl+C to stop status)"


def _getch() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _restore_sigint() -> None:
    """preexec_fn: restore default SIGINT in the child so Ctrl+C works for it."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python3 -m fob.status_viewer <cp-script> [args...]")
        sys.exit(1)

    cp_script = sys.argv[1]
    extra = sys.argv[2:]

    while True:
        # Enter alternate screen — subprocess output stays here, no scrollback.
        sys.stdout.write(_ALT_ON)
        sys.stdout.flush()

        # Parent ignores SIGINT while child runs; child gets SIG_DFL via preexec_fn.
        old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            subprocess.run(
                [cp_script, "status"] + extra,
                preexec_fn=_restore_sigint,
            )
        finally:
            signal.signal(signal.SIGINT, old_handler)

        # Disable any mouse modes Rich left enabled, then leave alternate screen.
        sys.stdout.write(_MOUSE_OFF + _ALT_OFF + "\n" + _HELP + "\n")
        sys.stdout.flush()

        key = _getch()
        if key in ("q", "Q", "\x1b"):
            break


if __name__ == "__main__":
    main()
