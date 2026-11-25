"""Read single key presses from the terminal, without waiting for Enter.

Normally a terminal hands a program a whole line only after Enter is pressed.
For the live timer the game needs every key the moment it is pressed, so this
module switches the terminal into "cbreak" mode while a mini-game runs:

    with KeyReader() as keys:
        key = keys.read(timeout=0.05)   # one character, or None if no key yet

Works on macOS and Linux (termios) and on Windows (msvcrt). Ctrl+C still quits.
"""

from __future__ import annotations

import os
import sys
import time

try:  # macOS / Linux
    import select
    import termios
    import tty

    _WINDOWS = False
except ImportError:  # Windows
    import msvcrt

    _WINDOWS = True


def live_keys_supported() -> bool:
    """True when we are in a real interactive terminal (not piped input)."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def enable_ansi() -> None:
    """Let the Windows console understand colour and cursor codes."""
    if _WINDOWS:
        os.system("")  # a known trick that turns on ANSI handling in cmd.exe


class KeyReader:
    def __enter__(self) -> "KeyReader":
        if not _WINDOWS:
            self._fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc) -> None:
        if not _WINDOWS:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def read(self, timeout: float | None = None) -> str | None:
        """Wait up to `timeout` seconds (None = forever) for one key."""
        if _WINDOWS:
            deadline = None if timeout is None else time.monotonic() + timeout
            while not msvcrt.kbhit():
                if deadline is not None and time.monotonic() >= deadline:
                    return None
                time.sleep(0.01)
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):  # arrow / function key: skip its second half
                msvcrt.getwch()
                return None
            return key
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return None
        key = os.read(self._fd, 1).decode(errors="ignore")
        if key == "\x1b":  # arrow keys send ESC [ A etc.: throw the rest away
            while select.select([sys.stdin], [], [], 0)[0]:
                os.read(self._fd, 1)
            return None
        return key
