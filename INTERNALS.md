# Internal notes

Miscellaneous implementation notes that are deliberately not part of the
public-facing documentation.

## Hidden games

Two games are reachable only by knowing the URL, and only when signed in.
Neither appears in the navigation.

### Packet Storm

`/packetstorm` is a Wi-Fi themed Asteroids game. It is always available to a
signed-in user.

### Beacon

`/beacon` is Doom (id Software, 1993), running the GPL engine source on the
vendored Emscripten port (see
[`wlanpi_webui/static/vendor/beacon/`](wlanpi_webui/static/vendor/beacon/README.md))
with the Freedoom Phase 1 IWAD. The URL, folder, and file names use an opaque
`beacon` codename so the page is not obvious from the address bar.

It is armed after reaching level 8 of Packet Storm (the first 6 GHz level), which
POSTs `/beacon/arm` and writes a device-wide flag file. The arming is per device,
not per browser.

The flag lives at `/var/lib/wlanpi-webui/beacon` (override with
`WLANPI_WEBUI_BEACON_FLAG`). It is read on every request, so disarming needs no
restart:

```bash
sudo rm /var/lib/wlanpi-webui/beacon
```

The dashboard tile and `/beacon` disappear immediately.

The game data is installed by the package to
`/usr/share/wlanpi-webui/beacon/data.wad` (override with
`WLANPI_WEBUI_BEACON_DATA`). If it is missing, `/beacon` explains how to install
it instead of 404ing. Build without it using `BEACON_SKIP_DATA=1`.

#### Development

```bash
# force-arm without playing (never set this in production)
WLANPI_WEBUI_BEACON_FORCE_UNLOCK=1

# enable the Packet Storm level-jump debug keys (] next, [ previous)
WLANPI_WEBUI_GAME_DEBUG=1
```

The level jump is inert unless `GAME_DEBUG` (or Flask debug) is set.

Doom, Doom II, and related marks are trademarks of id Software / ZeniMax. No id
artwork or wordmark is used anywhere in this project. The engine is GPL-2.0;
source availability is documented in the vendored README.
