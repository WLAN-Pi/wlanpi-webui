# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Flask WebUI that runs locally on a WLAN Pi device. In production it is deployed as a Debian package (dh-virtualenv) and served as: nginx (proxy, :443) → gunicorn (WSGI) → Flask app. Much of the code shells out to systemd, dpkg, and WLAN Pi scripts, so most features only fully work on an actual WLAN Pi.

## Commands

```bash
# Run tests (pytest + coverage via tox; py39 is the target)
tox
# Single test file / test
tox -- tests/test_utils.py
tox -- tests/test_utils.py::test_name

# Lint (mypy + ruff check + ruff format --check) — run before PRs
tox -e lint

# Format (ruff format) — run before PRs
tox -e format

# Run dev server (Flask debug mode, port 5000)
python -m wlanpi_webui
# or the production-style entrypoint
gunicorn wlanpi_webui.wsgi:app --bind 0.0.0.0

# Build the Debian package (on a build host with dh-virtualenv etc.)
dpkg-buildpackage -us -uc -b
```

Tool configs (ruff, mypy, black/isort, coverage, pyright) all live in `pyproject.toml`. Target Python is 3.9.

## Architecture

- **App factory + blueprints**: `wlanpi_webui/app.py:create_app()` registers one blueprint per feature: `about`, `cockpit`, `grafana`, `kismet`, `librespeed`, `network`, `profiler`, `stream`, and `errors`. Each feature is a directory whose `__init__.py` creates `bp = Blueprint(...)` and then imports its routes module at the bottom (circular-import pattern) — follow this pattern when adding a feature.
- **htmx-driven UI**: Templates (`wlanpi_webui/templates/`, with `partials/` and `extends/`) use UIkit + htmx + hyperscript. Routes commonly check `is_htmx(request)` (from `wlanpi_webui/utils.py`) and return HTML fragments for htmx swaps rather than full pages. Side-menu fragments per service (e.g. `/kismet/side_menu`) render start/stop controls.
- **Service control via systemd**: `wlanpi_webui/utils.py` holds the helpers used everywhere: `system_service_running_state`, `start_stop_service`, `systemd_service_message`, `package_installed` (dpkg). Feature blueprints like kismet/grafana/cockpit mostly toggle systemd services and redirect to the service's own port (kismet :2501, cockpit :9090, grafana :3000).
- **wlanpi-core API**: Privileged operations go through the separate `wlanpi-core` REST API at `127.0.0.1:31415`, authenticated with an HMAC-SHA256 signature (`X-Request-Signature`) over `method\npath\nquery\nbody` using the shared secret at `/home/wlanpi/.local/share/wlanpi-core/secrets/shared_secret.bin`. See `generate_hmac_signature`/`make_api_request` in `utils.py`. Several features first check that the `wlanpi-core` service is running and return `wlanpi_core_warning` if not.
- **Config**: `wlanpi_webui/config.py` builds a `Config` class at import time (WLAN Pi version from `/etc/wlanpi-release`, package version from apt or `wlanpi_webui/__version__.py`). `app.py` caches template context (installed-package checks) keyed on dpkg status mtime with a 60s TTL.
- **Deployment/packaging**: `debian/` holds the dh-virtualenv packaging (version comes from `debian/changelog`; systemd unit is `debian/wlanpi-webui.service`). `install/etc/nginx/` holds the nginx site configs (main app + librespeed speedtest on :8081). `dev.sh` symlinks those configs and restarts services on a device.

## Notes

- Tests in `tests/` are minimal; `test_app.py` is effectively empty.
- CI (`.github/workflows/`) builds the Debian package across Debian releases and deploys to packagecloud; there is no CI lint/test gate, so run `tox` and `tox -e lint` yourself.
- Per CONTRIBUTING.md, discuss significant changes with the WLAN Pi team before opening a PR, and lint/format before submitting.
