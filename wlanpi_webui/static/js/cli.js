/* Interactive shell on the /cli page.
 *
 * The WebUI runs one sync worker, so there is no WebSocket: the PTY lives on
 * the server and this polls for output. xterm.js renders it.
 *
 * This file is loaded on every page (see base.html) because htmx swaps the
 * page body in place: a script that ships with the swapped partial runs too
 * late to see the swap. The two vendored xterm files are pulled in on demand
 * so other pages do not pay for them.
 */
(function () {
  "use strict";

  var POLL_MS = 150;
  var current = null; // the live terminal's teardown, if any

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var el = document.createElement("script");
      el.src = src;
      el.onload = resolve;
      el.onerror = reject;
      document.head.appendChild(el);
    });
  }

  function ready(stage) {
    if (window.Terminal && window.FitAddon) {
      return Promise.resolve();
    }
    return loadScript(stage.getAttribute("data-xterm")).then(function () {
      return loadScript(stage.getAttribute("data-fit"));
    });
  }

  function init() {
    var stage = document.getElementById("cli-terminal");
    if (!stage || stage.dataset.started === "1") return;
    stage.dataset.started = "1";
    ready(stage).then(
      function () {
        start(stage);
      },
      function () {
        stage.textContent = "Could not load the terminal.";
      }
    );
  }

  // Leaving the page stops this terminal's polling, but the PTY stays on the
  // server so returning to /cli resumes it. Only a full page unload asks the
  // server to reap it (`kill`).
  function stopCurrent(kill) {
    if (current) {
      var teardown = current.teardown;
      current = null;
      teardown(kill);
    }
  }

  // xterm cannot use CSS variables directly, so read the theme tokens off the
  // document and hand them to it. Called again on every theme toggle.
  function termTheme() {
    var style = getComputedStyle(document.documentElement);

    function token(name, fallback) {
      return (style.getPropertyValue(name) || "").trim() || fallback;
    }

    return {
      background: token("--bg-surface", "#ffffff"),
      foreground: token("--text", "#222222"),
      cursor: token("--brand", "#f45625"),
    };
  }

  function start(stage) {
    var csrf = stage.getAttribute("data-csrf") || "";

    var term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      scrollback: 5000,
      theme: termTheme(),
    });
    var fit = new FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(stage);
    try {
      fit.fit();
    } catch (e) {
      /* ignore */
    }

    var offset = 0;
    var timer = 0;
    var stopped = false;

    function post(path, body) {
      return fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify(body || {}),
      });
    }

    function base64ToBytes(b64) {
      var bin = atob(b64);
      var out = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out;
    }

    function bytesToBase64(bytes) {
      var s = "";
      for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
      return btoa(s);
    }

    function sendResize() {
      try {
        fit.fit();
      } catch (e) {
        return;
      }
      post("/cli/resize", { rows: term.rows, cols: term.cols });
    }

    // The server reaps the shell after a spell with no input or output, so a
    // long idle leaves the terminal dead. Start a new one instead of going
    // quiet.
    function revive() {
      term.writeln("\r\n[session ended, starting a new shell]");
      offset = 0;
      post("/cli/start").then(
        function () {
          sendResize();
          timer = setTimeout(poll, POLL_MS);
        },
        function () {
          term.writeln("Could not start a new shell. Reload the page.");
        }
      );
    }

    function poll() {
      if (stopped) return;
      fetch("/cli/output?since=" + offset)
        .then(function (r) {
          return r.ok ? r.json() : null;
        })
        .then(function (data) {
          if (!data) throw new Error("no data");
          if (!data.alive) {
            revive();
            return;
          }
          offset = data.offset;
          if (data.data) term.write(base64ToBytes(data.data));
          timer = setTimeout(poll, POLL_MS);
        })
        .catch(function () {
          timer = setTimeout(poll, POLL_MS * 4);
        });
    }

    term.onData(function (data) {
      post("/cli/input", { data: bytesToBase64(new TextEncoder().encode(data)) });
    });

    function onThemeChange() {
      term.options.theme = termTheme();
    }

    function teardown(kill) {
      if (stopped) return;
      stopped = true;
      clearTimeout(timer);
      window.removeEventListener("resize", sendResize);
      document.removeEventListener("wlanpi:theme", onThemeChange);
      if (kill && navigator.sendBeacon) {
        navigator.sendBeacon("/cli/stop", new URLSearchParams({ csrf_token: csrf }));
      }
    }

    current = { teardown: teardown };
    window.addEventListener("resize", sendResize);
    document.addEventListener("wlanpi:theme", onThemeChange);

    post("/cli/start").then(
      function () {
        term.focus();
        sendResize();
        poll();
      },
      function () {
        term.writeln("Could not start the shell.");
      }
    );
  }

  document.addEventListener("htmx:afterSwap", init);
  document.addEventListener("htmx:beforeSwap", function (evt) {
    var target = evt.detail && evt.detail.target;
    if (
      target &&
      (target.id === "content" || (target.closest && target.closest("#content")))
    ) {
      stopCurrent(false);
    }
  });
  window.addEventListener("pagehide", function () {
    stopCurrent(true);
  });
  window.addEventListener("load", init);
})();
