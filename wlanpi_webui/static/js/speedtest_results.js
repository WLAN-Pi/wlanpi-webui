/* Draw a stored speedtest result as a copyable PNG card.
 *
 * Re-executing is harmless: the canvas is fully redrawn and the copy handler
 * is delegated from document.
 */
(function () {
  "use strict";

  var WIDTH = 640;
  var HEIGHT = 320;

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

  function drawStat(ctx, theme, cx, baseline, label, value) {
    ctx.fillStyle = theme.text;
    ctx.font = "600 44px " + theme.mono;
    ctx.textAlign = "center";
    ctx.fillText(fmt(value, ""), cx, baseline);

    ctx.fillStyle = theme.muted;
    ctx.font = "13px " + theme.sans;
    ctx.fillText(label, cx, baseline + 26);
  }

  function drawLatency(ctx, theme, y, label, ping, jitter) {
    ctx.font = "13px " + theme.sans;
    ctx.fillStyle = theme.muted;
    ctx.textAlign = "right";
    ctx.fillText(label, WIDTH / 2 - 12, y);

    ctx.fillStyle = theme.text;
    ctx.textAlign = "left";
    ctx.fillText(
      fmt(ping, "ms") + " ping   " + fmt(jitter, "ms") + " jitter",
      WIDTH / 2 + 12,
      y
    );
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

    ctx.fillStyle = theme.text;
    ctx.font = "600 18px " + theme.sans;
    ctx.textAlign = "left";
    ctx.fillText("WLAN Pi LibreSpeed", 24, 34);

    ctx.fillStyle = theme.muted;
    ctx.font = "12px " + theme.sans;
    ctx.textAlign = "right";
    ctx.fillText(result.tested_at || "", WIDTH - 24, 34);

    // The two numbers that matter, centred.
    drawStat(ctx, theme, WIDTH / 2 - 150, 150, "Download (Mbps)", result.download_mbps);
    drawStat(ctx, theme, WIDTH / 2 + 150, 150, "Upload (Mbps)", result.upload_mbps);

    // Latency, once. The gauges used to repeat the unloaded numbers.
    drawLatency(ctx, theme, 232, "Unloaded", result.ping_ms, result.jitter_ms);
    drawLatency(
      ctx,
      theme,
      262,
      "Loaded",
      result.loaded_ping_ms,
      result.loaded_jitter_ms
    );
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
