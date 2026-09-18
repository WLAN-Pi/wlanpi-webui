# Vendored frontend assets

These third-party assets are vendored (checked in) rather than loaded from a
CDN, so the WebUI works on an offline WLAN Pi. Versions are pinned exactly;
update them deliberately and record the new version + checksum here.

| Asset | Version | Source | Notes |
|---|---|---|---|
| `js/htmx.min.js` | 2.0.10 | `htmx.org@2.0.10` (`dist/htmx.min.js`) | npm `latest` tag. Do **not** jump to 4.x yet (see #100). |
| `js/_hyperscript.min.js` | 0.9.93 | `hyperscript.org@0.9.93` (`dist/_hyperscript.min.js`) | |
| `js/qrcode.min.js` | 1.0.0 | `qrcodejs@1.0.0` | Upstream is unmaintained; 1.0.0 is the latest release. |
| `js/uikit.js`, `js/uikit.min.js`, `js/uikit-icons.js`, `js/uikit-icons.min.js` | 3.25.23 | `uikit@3.25.23` (`dist/js/*`) | |
| `css/uikit.css`, `css/uikit.min.css`, `css/uikit-rtl.css`, `css/uikit-rtl.min.css` | 3.25.23 | `uikit@3.25.23` (`dist/css/*`) | |

`css/app.css`, `img/*` and `icon/*` are first-party assets, not vendored.

## Update procedure

```sh
# pick the version (latest within the current major), then:
npm pack htmx.org@2.0.10 uikit@3.25.23 hyperscript.org@0.9.93
tar xzf <pkg>.tgz
cp package/dist/... wlanpi_webui/static/...
sha256sum wlanpi_webui/static/js/* wlanpi_webui/static/css/uikit*
```

Then update the version table above, rebuild the package, and smoke-test the
UI (nav dropdowns, htmx navigation, start/stop buttons) on a device.

## Checksums (sha256)

```
71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de  js/htmx.min.js
e3591784abefb7491957cc93a395a063d04a0421822cf3cb22554faf474df78f  js/_hyperscript.min.js
c541ef06327885a8415bca8df6071e14189b4855336def4f36db54bde8484f36  js/qrcode.min.js
e573efef13c1bb09309c2e7baed3b186ebd741470d3068e7c09b192b0e9c0c79  js/uikit.js
ebd08b429283fd1fcf59face8edfe76108379c18b4f753893ccfb94a505afc27  js/uikit.min.js
e97c9411e574d1a9b17de0b8637cff4ffbac34a55ec0ea7b2239273e9fd906ba  js/uikit-icons.js
5de2207df75c0c0e992082c27f4ab242d446c3c93bed08322476ce5c52b50f6e  js/uikit-icons.min.js
96586b559fe73277067cecf6656d64f4975c5b5f1c21f21f7397589016a5c986  css/uikit.css
83036eb6b2571fefba32f9342511556b59127cff09877e4c559043287e3e9faf  css/uikit.min.css
2420d4dbbb194497dd12c838c9616223e541d2a9b66346790c6c7d9497759b8a  css/uikit-rtl.css
ee2f6203c15a72c7a00fe76c45c5ca7aa5a2677e630c8fb464581eb06cb4a298  css/uikit-rtl.min.css
```
