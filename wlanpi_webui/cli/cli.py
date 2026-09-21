"""wlanpi_webui.cli

A single interactive shell for the WebUI, served over HTTP polling.

The WebUI runs on one sync gunicorn worker, so a WebSocket is not an option.
Instead a real PTY is held in-process (one at a time) and the browser polls for
output. The shell runs as the WebUI's own user; there is no sudo.
"""

from __future__ import annotations

import base64
import fcntl
import os
import pty
import signal
import struct
import subprocess
import termios
import time

from flask import abort, jsonify, render_template, request

from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.cli import bp
from wlanpi_webui.utils import is_htmx

SHELL = "/bin/bash"
OUTPUT_LIMIT = 200_000  # bytes of scrollback kept per session
IDLE_TIMEOUT = 600  # seconds without input before the shell is reaped
BANNER = (
    b"\r\nRuns as the wlanpi user with no sudo. "
    b"The shell ends after 10 minutes idle.\r\n\r\n"
)


def _child_setup() -> None:
    """Make the PTY the shell's controlling terminal so job control works."""
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class Session:
    """One PTY-backed shell."""

    def __init__(self) -> None:
        master, slave = pty.openpty()
        self.fd = master
        self.proc = subprocess.Popen(
            [SHELL],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=os.environ.get("HOME") or "/home/wlanpi",
            preexec_fn=_child_setup,
            close_fds=True,
            env={**os.environ, "TERM": "xterm-256color"},
        )
        os.close(slave)
        os.set_blocking(self.fd, False)
        # Seed the banner into the read buffer: writing it to the fd would type
        # it into the shell instead.
        self.buffer = bytearray(BANNER)
        self.start = 0  # absolute offset of buffer[0]
        self.total = len(BANNER)  # absolute offset of the end
        self.last = time.time()

    def write(self, data: bytes) -> None:
        self.last = time.time()
        try:
            os.write(self.fd, data)
        except OSError:
            pass

    def resize(self, rows: int, cols: int) -> None:
        try:
            fcntl.ioctl(
                self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0)
            )
        except OSError:
            pass

    def drain(self) -> None:
        while True:
            try:
                chunk = os.read(self.fd, 65536)
            except (BlockingIOError, OSError):
                break
            if not chunk:
                break
            self.buffer.extend(chunk)
            self.total += len(chunk)
        if len(self.buffer) > OUTPUT_LIMIT:
            drop = len(self.buffer) - OUTPUT_LIMIT
            del self.buffer[:drop]
            self.start += drop

    def close(self) -> None:
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGHUP)
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except OSError:
                pass
        try:
            os.close(self.fd)
        except OSError:
            pass


_session: Session | None = None


def _current() -> Session | None:
    """The live session, reaping it once it has been idle too long."""
    global _session
    if _session is not None and time.time() - _session.last > IDLE_TIMEOUT:
        _session.close()
        _session = None
    return _session


@bp.route("/cli")
def cli():
    if is_htmx(request):
        return render_template("/partials/cli.html")
    return render_template("/extends/cli.html")


@bp.route("/cli/start", methods=["POST"])
@csrf_required
def start():
    """Start a fresh shell, replacing any existing one (single session)."""
    global _session
    if _session is not None:
        _session.close()
    _session = Session()
    _session.drain()
    return jsonify({"ok": True})


@bp.route("/cli/input", methods=["POST"])
@csrf_required
def send_input():
    session = _current()
    if session is None:
        abort(409)
    payload = request.get_json(silent=True) or {}
    try:
        data = base64.b64decode(payload.get("data") or "", validate=True)
    except (ValueError, TypeError):
        abort(400)
    session.write(data)
    return "", 204


@bp.route("/cli/resize", methods=["POST"])
@csrf_required
def resize():
    session = _current()
    if session is None:
        abort(409)
    payload = request.get_json(silent=True) or {}
    try:
        rows = int(payload.get("rows") or 0)
        cols = int(payload.get("cols") or 0)
    except (TypeError, ValueError):
        abort(400)
    session.resize(max(1, min(rows, 500)), max(1, min(cols, 500)))
    return "", 204


@bp.route("/cli/output")
def output():
    """Return the output the browser has not seen yet, as base64."""
    session = _current()
    if session is None:
        # `alive` lets the browser tell a reaped session (idle timeout) from a
        # quiet one, so it can start a new shell instead of sitting dead.
        return jsonify({"offset": 0, "data": "", "alive": False})

    session.drain()
    since = request.args.get("since", type=int)
    if since is None or since < session.start or since > session.total:
        since = session.start
    chunk = bytes(session.buffer[since - session.start :])
    return jsonify(
        {
            "offset": session.total,
            "data": base64.b64encode(chunk).decode("ascii"),
            "alive": True,
        }
    )


@bp.route("/cli/stop", methods=["POST"])
@csrf_required
def stop():
    global _session
    if _session is not None:
        _session.close()
        _session = None
    return "", 204
