# UI redesign plan

Status: agreed. Prerequisites #99 (PAM session login) and #101 (vendored
asset pin) are merged. Prep work (below) is on its own branches; the phased
UI work starts after that.

## Prep (before Phase 1)

- `chore/bump-python-deps`: refresh pinned runtime dependencies
  (`pip-compile`, Python 3.13).
- `chore/ruff-migration`: migrate lint/format to ruff with a mypy gate,
  matching wlanpi-core / wlanpi-mcp.

## Goal

Make login/session a first-class part of the UI and give the WebUI a light
visual refresh — without migrating frameworks or adding a build step.

## Non-goals

- No framework migration (UIKit 3 stays).
- No Node/CSS build step (assets stay vendored, app works offline).
- No change-password UI in the user menu. The backend only supports the
  first-boot *expired* password flow (`/change_password`); general password
  changes are done over SSH/Cockpit.
- Not a full visual redesign. Tailwind/major rewrite is postponed unless we
  later choose the full-redesign scope (see "Tailwind" below).

## Decisions

| Topic | Decision |
|---|---|
| Scope | Login/session UX + light refresh |
| CSS | Keep UIKit 3, buildless; add a small design-token layer |
| Login | Dedicated branded page (shared `auth/base.html`) |
| Home | Dashboard at `/`; LibreSpeed moves to `/speedtest/librespeed` |
| Session features | User menu, expiry redirect, idle auto-logout, toasts, dark/light toggle |
| Idle timeout | 4h sliding, env-configurable (`WLANPI_WEBUI_IDLE_TIMEOUT`) |
| Session key | Persist to disk (survives `systemctl restart`), sign out on reboot |
| Reboot logout | Compare `/proc/sys/kernel/random/boot_id` stored at login |
| Delivery | One tracking issue + phase-sized PRs (not one big PR) |

### Why not Tailwind

It is a rewrite, not a restructure: UIKit classes are hardcoded in
`base.html`, every `partials/`/`extends/` template, and Python-generated HTML
strings in the profiler/kismet/grafana menu views. It also needs a Node build
step in a deliberately buildless, offline-first repo, and dark mode still
costs the same (surface area, not framework). A design-token layer gives
~80% of Tailwind's daily value for ~1% of the migration cost. If we later
choose a full visual redesign, revisit this and migrate deliberately.

## Design-token layer (~80% of Tailwind's daily value)

Plain CSS custom properties in `app.css`. UIKit stays the component engine;
tokens only color/shape it. UIKit already provides grid/flex/spacing
utilities, so we add only the few it lacks.

Colors:

```
--brand #f45625   --brand-hover   --brand-contrast
--bg-page         --bg-surface    --navbar-bg   --navbar-text
--text            --text-muted    --border
--danger --warning --success --info   --focus-ring
```

Spacing / shape:

```
--space-1 4px --space-2 8px --space-3 12px --space-4 16px
--space-5 24px --space-6 32px --container 980px
--radius-sm --radius-md   --shadow-sm --shadow-md
```

Utilities (small set, only where UIKit has gaps):

```
.bg-page .bg-surface .bg-brand
.text-dim .text-brand
.radius-sm .radius-md
.shadow-sm .shadow-md
.visually-hidden
.auth-shell        # centered, token-driven container for auth pages
```

Plus a bounded set (<= ~15) of small mappings from UIKit components
(card, navbar, dropdown, button, input, alert) to tokens.

Dark theme is a `[data-theme="dark"]` override of the same tokens. The
toggle itself ships with the user menu in Phase 2.

## Phases

Each phase is its own PR referencing the tracking issue, merged
sequentially after #99 and #101.

### Phase 1 — tokens + branded auth
- Add tokens + UIKit mappings to `app.css`; swap hardcoded colors in
  `base.html` (`#222`, `#f45625`) for tokens.
- Add `templates/auth/base.html` (minimal branded document: logo, product
  name, footer) and have `login.html` / `change_password.html` extend it.
- Rebrand both auth pages with tokens; keep the `?reason=expired` notice in
  an `.auth-shell` card.
- Fix the broken PWA `manifest.json` icon paths.
- Tests: auth base renders; token classes present; `?reason` copy covered.

### Phase 2 — session UX
- Navbar user menu: "Signed in as <user>", theme toggle, logout. Expose
  `current_user` via a context processor (handle `None` on error pages).
- Expiry redirect: client-side; `htmx:beforeSwap` detects a response
  redirected to `/login` and does a full `window.location` to
  `/login?reason=expired` (guard against the 2s stats poll firing many
  redirects). No nginx change.
- Idle + reboot logout in one `before_request` hook, running for all
  endpoints (including `/auth/check`) before the access-control gate:
  - `session["boot_id"]` set at login; mismatch => clear (reboot logout).
  - `session["last_seen"]` updated on activity only; background pollers
    excluded (`stream.stats` and the `*_menu` endpoints). Clear when older
    than the idle timeout.
  - `SESSION_REFRESH_EACH_REQUEST = False`, `PERMANENT_SESSION_LIFETIME =
    idle timeout`, so the cookie slides only on activity.
  - Env config `WLANPI_WEBUI_IDLE_TIMEOUT`, default 4h.
- Persist the Flask signing key to `/var/lib/wlanpi-webui/session_key`
  (`0600`, `wlanpi`), created on first run; removed on purge. Random if
  unreadable.
- Toast helper `window.wlanpiToast()` in `app.js` (loaded non-deferred in
  `base.html` and the auth pages); replace the inline `<script>`
  notifications in `utils.py`.
- Tests: idle expiry, boot_id mismatch, persisted key across app
  instances, and that a background poll does not re-issue the cookie.

### Phase 3 — dashboard at `/` (done; #108 folded in)
- Reclaim `/`: remove `@bp.route("/")` from the librespeed blueprint.
- New dashboard blueprint at `/`: a Flipper Zero-style tile launcher
  (hostname/mode status strip, app tiles, version footer). Tiles are
  launchers — Speed Test same-tab, Kismet/Grafana/Cockpit new tab,
  Profiler/Network in-app.
- New Apps page (`/apps`) consolidating control for Speed Test, Profiler,
  Kismet, Grafana and Cockpit, and a Settings page (`/settings`) for About,
  the dark-mode toggle, Debug and logout. The per-app navbar dropdowns are
  gone; the navbar is HOME / APPS / NETWORK plus a settings gear.
- No iframes: Cockpit and the Kismet/Grafana UIs open in a new tab; Speed
  Test navigates in the same tab and links back home.
- Migrate the `/network` cards from the bash scripts to the same core API
  (reachability, public IP, eth0 IP config, LLDP/CDP neighbours).

### Phase 4 — dark sweep (timeboxed, skippable)
- Apply the dark token values across the remaining views (cards, forms,
  tables, navbar, dropdowns, modals, offcanvas, alerts).
- If it cannot be bounded, drop it and close the tracker.

## Session model (detail)

- Key persisted so `systemctl restart wlanpi-webui` / package upgrades do
  not log users out.
- `boot_id` stored at login; a reboot changes it, so everyone is signed out
  (like a fresh sudo session).
- Idle: activity requests update `last_seen` and re-issue the cookie with a
  fresh expiry; background pollers never do, so an open-but-idle tab still
  times out after 4h. No client heartbeat — a user who only reads without
  interacting re-logs in after 4h.

## Verification

- pytest + Flask test client for session logic (idle, boot_id, persisted
  key, background-poll no-refresh), with an injected clock (no `freezegun`).
- Local headless-Chromium harness (mock server) for theme persistence,
  toast, and the expiry redirect.
- Build the `.deb` and install on the test VM before any push.

## Deliberate simplifications (shortcut)

- `shortcut:` key persisted on disk; ceiling: any wlanpi-level code exec can
  forge sessions until reboot; upgrade: scheduled key rotation.
- `shortcut:` idle detection is coarse and fail-open when `/proc` is
  unreadable; upgrade: fail-closed.
- `shortcut:` dark theme covers shell/cards/forms only; ceiling: exotic
  UIKit widgets unstyled; upgrade: full component audit.
- `shortcut:` no heartbeat — reading-only sessions idle out after 4h;
  upgrade: add a throttled activity heartbeat if users complain.
