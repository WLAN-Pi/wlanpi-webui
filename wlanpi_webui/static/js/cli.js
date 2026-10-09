/* Interactive shell on the /cli page.
 *
 * The WebUI's gunicorn worker has no WebSocket support: the PTY lives on
 * the server and this polls for output. xterm.js renders it.
 *
 * This file is loaded on every page (see base.html) because htmx swaps the
 * page body in place: a script that ships with the swapped partial runs too
 * late to see the swap. The vendored xterm files (script, fit addon, CSS) are
 * pulled in on demand so other pages do not pay for them.
 */
(function () {
  "use strict";

  var POLL_MS = 150;
  var current = null; // the live terminal's teardown, if any

  // One load per URL, shared by every visit to /cli; a failed load is
  // forgotten so the next visit retries.
  var loads = {};

  function load(tag, url) {
    if (!loads[url]) {
      loads[url] = new Promise(function (resolve, reject) {
        var el = document.createElement(tag);
        if (tag === "link") {
          el.rel = "stylesheet";
          el.href = url;
        } else {
          el.src = url;
        }
        el.onload = resolve;
        el.onerror = function () {
          delete loads[url];
          el.remove();
          reject();
        };
        document.head.appendChild(el);
      });
    }
    return loads[url];
  }

  // xterm measures its cells when it opens, so its CSS must be in first.
  function ready(stage) {
    return Promise.all([
      load("link", stage.getAttribute("data-xterm-css")),
      load("script", stage.getAttribute("data-xterm")).then(function () {
        return load("script", stage.getAttribute("data-fit"));
      }),
    ]);
  }

  function init() {
    var stage = document.getElementById("cli-terminal");
    if (!stage || stage.dataset.started === "1") return;
    stage.dataset.started = "1";
    ready(stage).then(
      function () {
        // The user may have left /cli while the files loaded.
        if (stage.isConnected) start(stage);
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

  // xterm's stock ANSI colours are tuned for black: on the light surface its
  // bright green is 1.6:1, and on the dark surface blue and red fall under 3:1.
  // Each palette keeps every colour but black at 4.5:1 or better on its own
  // --bg-surface (#ffffff light, #1a2026 dark).
  var ANSI = {
    light: {
      black: "#24292f", red: "#b31d28", green: "#22863a", yellow: "#8a6100",
      blue: "#0550ae", magenta: "#8250df", cyan: "#0e7490", white: "#57606a",
      brightBlack: "#57606a", brightRed: "#a40e26", brightGreen: "#1a7f37",
      brightYellow: "#7d5700", brightBlue: "#0969da", brightMagenta: "#7b3fbf",
      brightCyan: "#0b6a85", brightWhite: "#24292f",
    },
    dark: {
      black: "#6e7681", red: "#ff7b72", green: "#3fb950", yellow: "#d29922",
      blue: "#58a6ff", magenta: "#bc8cff", cyan: "#39c5cf", white: "#c9d1d9",
      brightBlack: "#8b949e", brightRed: "#ffa198", brightGreen: "#56d364",
      brightYellow: "#e3b341", brightBlue: "#79c0ff", brightMagenta: "#d2a8ff",
      brightCyan: "#56d4dd", brightWhite: "#f0f6fc",
    },
  };

  // xterm cannot use CSS variables directly, so read the theme tokens off the
  // document and hand them to it. Called again on every theme toggle.
  function termTheme() {
    var style = getComputedStyle(document.documentElement);

    function token(name, fallback) {
      return (style.getPropertyValue(name) || "").trim() || fallback;
    }

    var dark = document.documentElement.getAttribute("data-theme") === "dark";
    return Object.assign(
      {
        background: token("--bg-surface", "#ffffff"),
        foreground: token("--text", "#222222"),
        cursor: token("--brand", "#f45625"),
        selectionBackground: dark ? "#3a4652" : "#cfe3ff",
      },
      dark ? ANSI.dark : ANSI.light
    );
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

    // One input request at a time: the server handles requests on several
    // threads, so parallel keystroke POSTs could reach the shell out of
    // order. Keys typed while a request is in flight go in the next batch.
    // A batch that fails is dropped, not replayed: the usual cause is a shell
    // that was reaped, and its replacement should not receive stale keys.
    var pendingInput = "";
    var sendingInput = false;
    function flushInput() {
      if (stopped || sendingInput || !pendingInput) return;
      var data = pendingInput;
      pendingInput = "";
      sendingInput = true;
      post("/cli/input", { data: bytesToBase64(new TextEncoder().encode(data)) })
        .then(
          function (r) {
            if (!r.ok && r.status !== 409) {
              term.writeln("\r\n[input not delivered: HTTP " + r.status + "]");
            }
          },
          function () {
            term.writeln("\r\n[input not delivered: connection lost]");
          }
        )
        .then(function () {
          sendingInput = false;
          flushInput();
        });
    }

    term.onData(function (data) {
      pendingInput += data;
      flushInput();
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
