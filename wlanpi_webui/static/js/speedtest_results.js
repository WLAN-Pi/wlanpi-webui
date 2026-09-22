/* Draw a stored speedtest result as a copyable PNG card.
 *
 * Re-executing is harmless: the canvas is fully redrawn and the copy handler
 * is delegated from document.
 */
(function () {
  "use strict";

  var WIDTH = 1200;
  var HEIGHT = 630;

  function token(name, fallback) {
    var value = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (value || "").trim() || fallback;
  }

  function num(value) {
    return typeof value === "number" && isFinite(value) ? value : null;
  }

  function fmt(value, unit) {
    return num(value) === null ? "n/a" : value.toFixed(2) + (unit ? " " + unit : "");
  }

  // The WLAN Pi mark, drawn from the same 24x24 bolt used on the dashboard, so
  // it can be tinted with the theme text colour instead of a raster asset.
  function drawBolt(ctx, x, y, size, color) {
    var s = size / 24;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(s, s);
    ctx.beginPath();
    ctx.moveTo(13.5, 2.5);
    ctx.lineTo(7.5, 12.5);
    ctx.lineTo(11.5, 12.5);
    ctx.lineTo(9.5, 19.5);
    ctx.lineTo(16.5, 9.5);
    ctx.lineTo(12.5, 9.5);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.restore();
  }

  function drawHeader(ctx, theme, testedAt) {
    drawBolt(ctx, 64, 64, 44, theme.text);

    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = theme.text;
    ctx.font = "700 34px " + theme.sans;
    ctx.fillText("WLAN Pi", 124, 100);
    var markWidth = ctx.measureText("WLAN Pi").width;

    ctx.fillStyle = theme.muted;
    ctx.font = "400 22px " + theme.sans;
    ctx.fillText("LibreSpeed", 124 + markWidth + 14, 100);

    ctx.textAlign = "right";
    ctx.fillStyle = theme.muted;
    ctx.font = "18px " + theme.sans;
    ctx.fillText(testedAt || "", WIDTH - 64, 100);
  }

  function drawStat(ctx, theme, cx, label, value) {
    ctx.textAlign = "center";
    ctx.fillStyle = theme.text;
    ctx.font = "700 92px " + theme.mono;
    ctx.fillText(fmt(value, ""), cx, 320);

    ctx.fillStyle = theme.muted;
    ctx.font = "20px " + theme.sans;
    ctx.fillText(label, cx, 372);
  }

  function drawLatencyColumn(ctx, theme, cx, heading, ping, jitter) {
    ctx.textAlign = "center";

    ctx.fillStyle = theme.text;
    ctx.font = "600 24px " + theme.sans;
    ctx.fillText(heading, cx, 470);

    ctx.fillStyle = theme.muted;
    ctx.font = "20px " + theme.mono;
    ctx.fillText(fmt(ping, "ms") + " ping", cx, 512);
    ctx.fillText(fmt(jitter, "ms") + " jitter", cx, 546);
  }

  function draw(canvas) {
    var raw = canvas.getAttribute("data-result");
    if (!raw) return;
    var result;
    try {
      result = JSON.parse(raw);
    } catch (e) {
      return;
    }

    var dpr = window.devicePixelRatio || 1;
    canvas.width = WIDTH * dpr;
    canvas.height = HEIGHT * dpr;
    canvas.style.width = "100%";
    canvas.style.maxWidth = WIDTH + "px";

    var ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    var theme = {
      surface: token("--bg-surface", "#ffffff"),
      text: token("--text", "#222222"),
      muted: token("--text-muted", "#595959"),
      border: token("--border", "#e5e5e5"),
      mono: token("--font-mono", "monospace"),
      sans: token("--font-sans", "sans-serif"),
    };

    ctx.fillStyle = theme.surface;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.strokeStyle = theme.border;
    ctx.lineWidth = 2;
    ctx.strokeRect(1, 1, WIDTH - 2, HEIGHT - 2);

    drawHeader(ctx, theme, result.tested_at);

    ctx.strokeStyle = theme.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(64, 140);
    ctx.lineTo(WIDTH - 64, 140);
    ctx.stroke();

    // The two numbers that matter, centred in their own columns.
    var left = WIDTH * 0.3;
    var right = WIDTH * 0.7;
    drawStat(ctx, theme, left, "Download (Mbps)", result.download_mbps);
    drawStat(ctx, theme, right, "Upload (Mbps)", result.upload_mbps);

    // Latency as two centred columns so Unloaded and Loaded read as one block.
    drawLatencyColumn(ctx, theme, left, "Unloaded", result.ping_ms, result.jitter_ms);
    drawLatencyColumn(
      ctx,
      theme,
      right,
      "Loaded",
      result.loaded_ping_ms,
      result.loaded_jitter_ms
    );

    ctx.beginPath();
    ctx.moveTo(64, 578);
    ctx.lineTo(WIDTH - 64, 578);
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.fillStyle = theme.muted;
    ctx.font = "18px " + theme.sans;
    ctx.fillText("wlanpi.com", WIDTH / 2, 612);
  }

  function renderAll() {
    document.querySelectorAll("canvas.result-image").forEach(draw);
  }

  function download(blob) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "wlanpi-speedtest.png";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  // Encoding and the clipboard write are both async, so a second click lands
  // before the first finishes and toasts again. Guard on time, not on the
  // button's disabled state: toBlob can resolve between the two clicks.
  var COPY_GUARD_MS = 1500;
  var lastCopyAt = 0;

  function copyCanvas(canvas, btn) {
    var now = Date.now();
    if (now - lastCopyAt < COPY_GUARD_MS) return;
    lastCopyAt = now;

    function finish(ok) {
      if (window.wlanpiToast) {
        window.wlanpiToast(
          ok ? "Copied result image." : "Could not copy result image.",
          ok ? "success" : "warning"
        );
      }
    }

    canvas.toBlob(function (blob) {
      if (!blob) {
        finish(false);
        return;
      }
      if (navigator.clipboard && window.ClipboardItem && window.isSecureContext) {
        navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]).then(
          function () {
            finish(true);
          },
          function () {
            download(blob);
            finish(true);
          }
        );
      } else {
        download(blob);
        finish(true);
      }
    }, "image/png");
  }

  document.addEventListener("click", function (evt) {
    var btn = evt.target.closest("[data-copy-result]");
    if (!btn) return;
    var card = btn.closest(".speedtest-result-card");
    var canvas = card ? card.querySelector("canvas.result-image") : null;
    if (canvas) copyCanvas(canvas, btn);
  });

  document.addEventListener("htmx:afterSwap", renderAll);
  window.addEventListener("load", renderAll);
})();
