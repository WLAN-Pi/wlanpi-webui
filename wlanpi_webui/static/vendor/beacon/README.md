# Vendored engine

This directory vendors a prebuilt WebAssembly engine used by the hidden
`/beacon` page. It is **not** a runtime dependency and there is no build step in
the WebUI. The files are checked in; treat them as code we now own.

## Upstream

- Project: [cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm) — a
  [Chocolate Doom](https://github.com/chocolate-doom/chocolate-doom) port to
  WebAssembly with WebSockets support.
- Pinned commit: `65e0d3ae2ffa604155eebd96ed40da6567bd08f4`
- License: GNU General Public License v2.0. See `COPYING.md` (retained from
  upstream). Source availability: upstream source is at the commit above; the
  local modifications are described below and in this file.

Doom, Doom II, and the id Software / ZeniMax marks are trademarks of their
owners. No id artwork, logo, or wordmark is used in this WebUI. The engine is
GPL code and is served as a static asset, separate from the WebUI's own code.

## Files

| File | sha256 |
|---|---|
| `beacon.js` | `f973828f988343c6b8a47fa39ba474dd407f8f8ffcc661284d7fccd6adc044b9` |
| `beacon.wasm` | `64866c990952abfe084ddf3bd1c6bb323cfe9ee234d560171ae2898d55e978ef` |

The files were renamed from upstream's `websockets-doom.{js,wasm}` to opaque
names, and `beacon.js`'s internal `wasmBinaryFile` reference was updated to
match. This is the only change to the compiled output.

The game data is **not** vendored. See `debian/rules`; it is fetched at package
build time and installed to `/usr/share/wlanpi-webui/beacon/data.wad`. The 1997
GPL source release covered the engine code only, not the original game data, so
no id WAD is ever shipped.

## Local modifications

Built from the pinned commit with Emscripten **3.1.43** (newer SDKs reject the
2021-era flags). Two changes to `configure.ac`:

1. `EMFLAGS` — dropped `-gsource-map` / `--source-map-base` (smaller output,
   full Binaryen optimization), removed deprecated/unsafe flags, raised memory
   for full-size game data, and switched to the current runtime-method export:

   ```
   -s INVOKE_RUN=1 -s USE_SDL=2 -s USE_SDL_MIXER=2 -s USE_SDL_NET=2 -s WASM=1 \
   -s ALLOW_MEMORY_GROWTH=1 -s INITIAL_MEMORY=67108864 -s MAXIMUM_MEMORY=536870912 \
   -s FORCE_FILESYSTEM=1 -s EXTRA_EXPORTED_RUNTIME_METHODS=[['FS','ccall']] \
   -s EXIT_RUNTIME=1 -s ERROR_ON_UNDEFINED_SYMBOLS=0 -s ASYNCIFY -O3
   ```

2. `CFLAGS` — dropped `-g` so Binaryen can fully optimize (DWARF otherwise
   limits post-link optimization).

The data file is loaded at runtime by `static/js/beacon.js`, which fetches it
from the gated `/beacon/data` route and writes it into the Emscripten filesystem
in `preRun` (via `addRunDependency`/`removeRunDependency`), instead of upstream's
`FS.createPreloadedFile` of a baked-in IWAD.

## Rebuilding

```sh
git clone https://github.com/cloudflare/doom-wasm
cd doom-wasm && git checkout 65e0d3ae2ffa604155eebd96ed40da6567bd08f4
# install and activate Emscripten 3.1.43, then apply the two configure.ac
# changes above, then:
./scripts/build.sh
# copy and rename src/websockets-doom.js -> beacon.js and
# src/websockets-doom.wasm -> beacon.wasm here, and update wasmBinaryFile.
```

Every browser port of this engine is a hobby project. Pin it, verify the
checksums above, and smoke-test on a device before bumping.
