/* WLAN Pi WebUI: theme toggle, toast helper and session-expiry handling. */
(function () {
  "use strict";

  // ---- Theme ----------------------------------------------------------
  // The stored preference is applied here, before the stylesheets are
  // evaluated, so there is no flash of the wrong theme.
  function syncThemeColor(theme) {
    try {
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) {
        meta.setAttribute(
          "content",
          theme === "dark" ? "#0b0f13" : "#f8f8f8"
        );
      }
    } catch (e) {
      /* ignore */
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    syncThemeColor(theme);
    try {
      localStorage.setItem("wlanpi-theme", theme);
    } catch (e) {
      /* storage unavailable; keep the in-page theme only */
    }
    try {
      // Cookie so the server can render the theme (no flash) and so it
      // survives when localStorage is unavailable.
      document.cookie =
        "wlanpi_theme=" + theme + "; path=/; max-age=31536000; SameSite=Lax";
    } catch (e) {
      /* ignore */
    }
    // Let components that cannot use CSS variables directly (the xterm
    // terminal) recolor themselves.
    document.dispatchEvent(
      new CustomEvent("wlanpi:theme", { detail: { theme: theme } })
    );
  }

  window.wlanpiToggleTheme = function () {
    var current =
      document.documentElement.getAttribute("data-theme") === "dark"
        ? "dark"
        : "light";
    applyTheme(current === "dark" ? "light" : "dark");
  };

  window.addEventListener("storage", function (evt) {
    if (
      evt.key === "wlanpi-theme" &&
      (evt.newValue === "dark" || evt.newValue === "light")
    ) {
      applyTheme(evt.newValue);
    }
  });

  try {
    var stored = localStorage.getItem("wlanpi-theme");
    if (stored === "dark" || stored === "light") {
      applyTheme(stored);
    } else if (
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
      // No stored preference: follow the OS on first visit.
      applyTheme("dark");
    } else {
      syncThemeColor(
        document.documentElement.getAttribute("data-theme") === "dark"
          ? "dark"
          : "light"
      );
    }
  } catch (e) {
    /* ignore */
  }

  // ---- Nav active state ------------------------------------------------
  // The server marks the active nav item on full loads; keep it in sync
  // for htmx in-app navigation too.
  function navSection(path) {
    if (/^\/(apps|profiler|kismet|grafana|cockpit|speedtest)/.test(path)) {
      return "apps";
    }
    if (path.indexOf("/cli") === 0) {
      return "cli";
    }
    if (path.indexOf("/network") === 0) {
      return "network";
    }
    if (path.indexOf("/system") === 0) {
      return "system";
    }
    if (path === "/") {
      return "home";
    }
    return "";
  }

  function syncNav(path) {
    var section = navSection(path);
    try {
      document.querySelectorAll("[data-nav]").forEach(function (link) {
        var on = link.getAttribute("data-nav") === section;
        var item = link.closest("li");
        if (item) {
          item.classList.toggle("uk-active", on);
        }
        if (on) {
          link.setAttribute("aria-current", "page");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    } catch (e) {
      /* ignore */
    }
  }

  document.addEventListener("htmx:pushedIntoHistory", function (evt) {
    if (evt.detail && evt.detail.path) {
      syncNav(evt.detail.path);
    }
  });

  // ---- Feed polling (network cards, system health) ----------------------
  // htmx has no native pause/interval control, so intervals live here.
  // Each feed polls via a custom trigger event; changing the select or
  // pausing restarts (or stops) its timer. Choice persists in localStorage.
  // Timers self-clear once their element leaves the page.
  window.wlanpiPollers = {};
  window.wlanpiPollPaused = {};

  function wlanpiStoredSecs(id, defSecs) {
    try {
      var s = localStorage.getItem("wlanpi-poll-" + id);
      if (s !== null && !isNaN(parseInt(s, 10))) {
        return parseInt(s, 10);
      }
    } catch (e) {
      /* ignore */
    }
    return defSecs;
  }

  function wlanpiFire(id, evt) {
    var el = document.getElementById(id);
    if (!el) {
      if (window.wlanpiPollers[id]) {
        clearInterval(window.wlanpiPollers[id]);
        delete window.wlanpiPollers[id];
      }
      return false;
    }
    if (window.htmx) {
      window.htmx.trigger(el, evt);
    }
    return true;
  }

  window.wlanpiStartPoll = function (id, evt, secs) {
    if (window.wlanpiPollers[id]) {
      clearInterval(window.wlanpiPollers[id]);
      delete window.wlanpiPollers[id];
    }
    try {
      localStorage.setItem("wlanpi-poll-" + id, String(secs));
    } catch (e) {
      /* ignore */
    }
    if (window.wlanpiPollPaused[id] || secs <= 0) {
      return;
    }
    window.wlanpiPollers[id] = setInterval(function () {
      wlanpiFire(id, evt);
    }, secs * 1000);
  };

  window.wlanpiTogglePoll = function (id, evt, btn) {
    window.wlanpiPollPaused[id] = !window.wlanpiPollPaused[id];
    var sel = document.querySelector('[data-poll-select="' + id + '"]');
    window.wlanpiStartPoll(
      id,
      evt,
      sel ? parseInt(sel.value, 10) : 15
    );
    if (btn) {
      btn.textContent = window.wlanpiPollPaused[id]
        ? "Resume refresh"
        : "Pause refresh";
      btn.setAttribute("aria-pressed", String(!!window.wlanpiPollPaused[id]));
    }
  };

  window.wlanpiInitPoll = function (id, evt, defSecs) {
    var secs = wlanpiStoredSecs(id, defSecs);
    var sel = document.querySelector('[data-poll-select="' + id + '"]');
    if (sel) {
      sel.value = String(secs);
    }
    var btn = document.querySelector('[data-poll-toggle="' + id + '"]');
    if (btn && window.wlanpiPollPaused[id]) {
      btn.textContent = "Resume refresh";
      btn.setAttribute("aria-pressed", "true");
    }
    window.wlanpiStartPoll(id, evt, secs);
  };

  window.wlanpiFirePoll = function (id, evt) {
    wlanpiFire(id, evt);
  };

  // ---- Card masonry -----------------------------------------------------
  // CSS grid keeps cards at their natural height; each card spans as many 8px
  // rows as it needs and grid-auto-flow: dense backfills the gaps under taller
  // cards. Re-run on load, resize, font load, and after every htmx swap.
  function layoutMasonry(container) {
    var children = container.children;
    if (!children.length) return;

    // Measure before enabling the 8px row track, so no card overlaps before
    // its span is applied.
    var heights = [];
    for (var i = 0; i < children.length; i++) {
      heights.push(children[i].offsetHeight);
    }

    container.classList.add("is-masonry");
    var styles = getComputedStyle(container);
    var gap = parseFloat(styles.rowGap || styles.gap) || 16;
    var row = 8;

    for (var j = 0; j < children.length; j++) {
      var span = Math.ceil((heights[j] + gap) / (row + gap));
      children[j].style.gridRowEnd = "span " + Math.max(1, span);
    }
  }

  window.wlanpiMasonry = function (root) {
    var containers = (root || document).querySelectorAll(".card-masonry");
    Array.prototype.forEach.call(containers, layoutMasonry);
  };

  var masonryTimer = 0;
  function scheduleMasonry() {
    clearTimeout(masonryTimer);
    masonryTimer = setTimeout(function () {
      window.wlanpiMasonry();
    }, 50);
  }

  // Lay out synchronously after a swap, before the browser paints, so cards
  // never flash in the row-aligned fallback grid; debounce only resize.
  document.addEventListener("htmx:afterSwap", function () {
    window.wlanpiMasonry();
  });
  window.addEventListener("load", function () {
    window.wlanpiMasonry();
  });
  window.addEventListener("resize", scheduleMasonry);
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      window.wlanpiMasonry();
    });
  }

  // ---- Toasts and notification history --------------------------------
  // Persisted in localStorage but keyed by the kernel boot id, so it
  // survives reloads and clears on device reboot. The /alerts page renders
  // the list with a fuzzy search.
  var NOTIF_KEY = "wlanpi-notifications";
  var NOTIF_MAX = 100;

  function bootId() {
    var m = document.querySelector('meta[name="wlanpi-boot-id"]');
    return m ? m.content : "";
  }

  function loadNotifications() {
    var data = null;
    try {
      data = JSON.parse(localStorage.getItem(NOTIF_KEY));
    } catch (e) {
      data = null;
    }
    if (!data || data.boot !== bootId() || !Array.isArray(data.items)) {
      data = { boot: bootId(), items: [] };
    }
    return data;
  }

  function saveNotifications(data) {
    try {
      localStorage.setItem(NOTIF_KEY, JSON.stringify(data));
    } catch (e) {
      /* ignore */
    }
  }

  function fuzzyMatch(text, query) {
    text = text.toLowerCase();
    query = query.toLowerCase();
    var i = 0;
    var j;
    for (j = 0; j < text.length && i < query.length; j++) {
      if (text.charAt(j) === query.charAt(i)) {
        i++;
      }
    }
    return i === query.length;
  }

  function renderNotifications(query) {
    var el = document.getElementById("notifications-list");
    if (!el) {
      return;
    }
    if (query === undefined) {
      var input = document.getElementById("notifications-search");
      query = input ? input.value : "";
    }
    var items = loadNotifications().items.slice().reverse();
    if (query) {
      items = items.filter(function (n) {
        return fuzzyMatch(n.message + " " + n.status, query);
      });
    }
    if (!items.length) {
      el.innerHTML =
        '<li class="uk-text-meta">' +
        (query ? "No matching messages." : "No messages yet.") +
        "</li>";
      return;
    }
    el.innerHTML = items
      .map(function (n) {
        return (
          '<li class="notification notification-' +
          n.status +
          '"><span class="notification-msg">' +
          n.message +
          '</span><span class="notification-time">' +
          new Date(n.t).toLocaleTimeString() +
          "</span></li>"
        );
      })
      .join("");
  }

  window.wlanpiFilterNotifications = function (query) {
    renderNotifications(query);
  };

  window.wlanpiToast = function (message, status) {
    status = status || "primary";
    var data = loadNotifications();
    data.items.push({ message: message, status: status, t: Date.now() });
    if (data.items.length > NOTIF_MAX) {
      data.items.shift();
    }
    saveNotifications(data);
    if (window.UIkit && UIkit.notification) {
      UIkit.notification({
        message: message,
        status: status,
        pos: "top-right",
        timeout: 8000,
      });
    }
    renderNotifications();
  };

  function fallbackCopyText(text) {
    if (!document.queryCommandSupported?.("copy")) return false;
    var input = document.createElement("textarea");
    input.textContent = text;
    input.style.position = "fixed";
    document.body.appendChild(input);
    input.select();
    try {
      document.execCommand("copy");
      return true;
    } catch (ex) {
      console.warn("Copy to clipboard failed.", ex);
      return false;
    } finally {
      document.body.removeChild(input);
    }
  }

  window.wlanpiCopyText = function (text, btn, label) {
    // `label` names what was copied, so the toast and the notification
    // history say what landed on the clipboard.
    var what = label || "text";

    function done(ok) {
      if (ok && btn) {
        btn.classList.add("copy-ok");
        setTimeout(function () {
          btn.classList.remove("copy-ok");
        }, 1500);
      }
      if (window.wlanpiToast) {
        window.wlanpiToast(
          ok ? "Copied " + what + " to clipboard." : "Could not copy " + what + ".",
          ok ? "success" : "warning"
        );
      }
      return ok;
    }

    if (navigator.clipboard?.writeText && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(
        function () {
          done(true);
        },
        function () {
          done(fallbackCopyText(text));
        }
      );
      return true;
    }
    return done(fallbackCopyText(text));
  };

  // ---- Power confirmation ---------------------------------------------
  // Reboot/shutdown open a UIkit "Are you sure?" modal; confirming submits the
  // matching form so htmx still performs the POST with its CSRF token.
  window.wlanpiConfirmPower = function (action) {
    var form = document.getElementById(action + "-form");
    if (!form) return;

    function submit() {
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else if (window.htmx) {
        window.htmx.trigger(form, "submit");
      } else {
        form.submit();
      }
    }

    var modalEl = document.getElementById("power-confirm");
    if (!window.UIkit || !modalEl) {
      if (window.confirm("Are you sure?")) submit();
      return;
    }

    var text = document.getElementById("power-confirm-text");
    if (text) {
      text.textContent =
        action === "reboot"
          ? "The WLAN Pi will reboot and the WebUI will disconnect. Are you sure?"
          : "The WLAN Pi will shut down and the WebUI will disconnect. Are you sure?";
    }
    var ok = document.getElementById("power-confirm-ok");
    if (ok) {
      ok.onclick = function () {
        window.UIkit.modal(modalEl).hide();
        submit();
      };
    }
    window.UIkit.modal(modalEl).show();
  };

  var ALERTS_SEEN_KEY = "wlanpi-alerts-seen";

  function alertsSeen() {
    try {
      var v = JSON.parse(localStorage.getItem(ALERTS_SEEN_KEY));
      return Array.isArray(v) ? v : [];
    } catch (e) {
      return [];
    }
  }

  function saveAlertsSeen(keys) {
    try {
      localStorage.setItem(ALERTS_SEEN_KEY, JSON.stringify(keys));
    } catch (e) {
      /* ignore */
    }
  }

  function alertKeysFrom(value) {
    return (value || "").split(",").filter(function (k) {
      return k.length > 0;
    });
  }

  // The bell badge counts active alerts the user has not looked at yet.
  // Stale keys are dropped, so a condition that clears and later returns is
  // unread again.
  function syncAlertsBell(keys) {
    var el = document.getElementById("alerts-bell");
    if (!el) return;
    var seen = alertsSeen().filter(function (k) {
      return keys.indexOf(k) !== -1;
    });
    saveAlertsSeen(seen);
    var unread = keys.filter(function (k) {
      return seen.indexOf(k) === -1;
    });
    var badge = el.querySelector(".alerts-badge");
    if (badge) {
      badge.textContent = String(unread.length);
      badge.hidden = unread.length === 0;
    }
  }

  // Called by the alerts page once its conditions are on screen.
  window.wlanpiMarkAlertsSeen = function (keys) {
    var seen = alertsSeen();
    keys.forEach(function (k) {
      if (seen.indexOf(k) === -1) seen.push(k);
    });
    saveAlertsSeen(seen);
    syncAlertsBell(keys);
  };

  // Server-queued toast (e.g. "Profiler started.") rides on a response header
  // so it survives the redirect back to the page the user came from. The same
  // hook carries the active-alert keys for the navbar bell.
  // Listen on document: app.js loads in <head>, so document.body is still
  // null when this file runs. htmx events bubble.
  document.addEventListener("htmx:afterSettle", function (evt) {
    var xhr = evt.detail && evt.detail.xhr;
    if (xhr && xhr.getResponseHeader) {
      var alerts = xhr.getResponseHeader("X-Wlanpi-Alerts");
      if (alerts !== null) {
        var bell = document.getElementById("alerts-bell");
        if (bell) bell.dataset.alertKeys = alerts;
        syncAlertsBell(alertKeysFrom(alerts));
      }
    }
    syncAlertsSeenFromPage();

    if (!xhr || !xhr.getResponseHeader) return;
    var raw = xhr.getResponseHeader("X-Wlanpi-Toast");
    if (!raw) return;
    var toast;
    try {
      toast = JSON.parse(raw);
    } catch (e) {
      return;
    }
    if (toast && toast.message) {
      window.wlanpiToast(toast.message, toast.status || "primary");
    }
  });

  function syncAlertsSeenFromPage() {
    var seenEl = document.getElementById("alerts-seen");
    if (seenEl) {
      window.wlanpiMarkAlertsSeen(alertKeysFrom(seenEl.dataset.keys));
    }
  }

  document.addEventListener("htmx:afterSwap", function () {
    renderNotifications();
  });
  window.addEventListener("load", function () {
    renderNotifications();
    syncAlertsSeenFromPage();
    var bell = document.getElementById("alerts-bell");
    if (bell) syncAlertsBell(alertKeysFrom(bell.dataset.alertKeys));
  });

  // Debug aid: fire a test toast from the query string, e.g.
  //   /about?toast=Hello&status=warning
  try {
    var params = new URLSearchParams(window.location.search);
    var toastMessage = params.get("toast");
    if (toastMessage) {
      var toastStatus = params.get("status") || "primary";
      window.addEventListener("load", function () {
        window.wlanpiToast(toastMessage, toastStatus);
      });
    }
  } catch (e) {
    /* ignore */
  }

  // ---- Session expiry -------------------------------------------------
  // nginx rewrites an expired session to a redirect to /login, which htmx
  // would otherwise swap into the page. Detect it and do a full navigation.
  var redirecting = false;

  function redirectToLogin() {
    if (redirecting) {
      return;
    }
    redirecting = true;
    window.location.assign("/login?reason=expired");
  }

  document.addEventListener("htmx:beforeSwap", function (evt) {
    var xhr = evt.detail && evt.detail.xhr;
    if (!xhr) {
      return;
    }
    var url = xhr.responseURL || "";
    if (xhr.status === 401 || url.indexOf("/login") !== -1) {
      evt.detail.shouldSwap = false;
      redirectToLogin();
    }
  });

  document.addEventListener("htmx:responseError", function (evt) {
    var xhr = evt.detail && evt.detail.xhr;
    if (xhr && xhr.status === 401) {
      redirectToLogin();
    }
  });

  // Kismet opens in a new tab, but only when the service is up; otherwise
  // tell the user instead of landing them on a dead port.
  window.wlanpiLaunchKismet = function (evt) {
    if (evt) {
      evt.preventDefault();
    }
    fetch("/kismet/status", { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (data && data.running) {
          window.open("/kismet", "_blank", "noopener");
        } else {
          window.wlanpiToast(
            "Kismet is not running. Start it from Applications.",
            "warning"
          );
        }
      })
      .catch(function () {
        window.wlanpiToast("Kismet status is unavailable.", "warning");
      });
  };

  // Grafana opens in a new tab, but only once its service is up and the web UI
  // is answering; otherwise toast the reason instead of a dead tab.
  window.wlanpiLaunchGrafana = function (evt) {
    if (evt) {
      evt.preventDefault();
    }
    fetch("/grafana/status", { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        var state = data && data.state;
        if (state === "running") {
          window.open("/grafana_url", "_blank", "noopener");
        } else if (state === "starting" || state === "waiting") {
          window.wlanpiToast(
            "Grafana is still starting. Try again in a moment.",
            "warning"
          );
        } else if (state === "stopping") {
          window.wlanpiToast(
            "Grafana is stopping. Try again in a moment.",
            "warning"
          );
        } else {
          window.wlanpiToast(
            "Grafana is not running. Start it from Applications.",
            "warning"
          );
        }
      })
      .catch(function () {
        window.wlanpiToast("Grafana status is unavailable.", "warning");
      });
  };

  // ---- Konami code ----------------------------------------------------
  // Hidden shortcut to /packetstorm. Ignores keystrokes in form fields,
  // never preventDefaults, and stays quiet when already there.
  (function () {
    var seq = [
      "ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown",
      "ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight",
      "b", "a",
    ];
    var pos = 0;
    document.addEventListener("keydown", function (evt) {
      var t = evt.target;
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.tagName === "SELECT" ||
          t.isContentEditable)
      ) {
        pos = 0;
        return;
      }
      pos = evt.key === seq[pos] ? pos + 1 : evt.key === seq[0] ? 1 : 0;
      if (pos === seq.length) {
        pos = 0;
        if (window.location.pathname === "/packetstorm" || !window.htmx) {
          return;
        }
        window.htmx.ajax("GET", "/packetstorm", {
          target: "#content",
          swap: "innerHTML",
          pushUrl: true,
        });
      }
    });
  })();

  // ---- Hidden launcher tiles ------------------------------------------
  // Packet Storm is hidden until the faint glyph in the launcher footer is
  // tapped. The hidden game's tile additionally needs the device unlock (the
  // server only renders it when armed), so it appears once Packet Storm is
  // visible AND the level-8 unlock has happened. The reveal is permanent.
  (function () {
    var KEY = "wlanpi:packetstorm:found";

    function isFound() {
      try {
        return window.localStorage.getItem(KEY) === "1";
      } catch (e) {
        return false;
      }
    }

    var revealed = false;

    function setRevealed(on) {
      revealed = on;
      var storm = document.getElementById("packetstorm-tile");
      if (storm) {
        storm.hidden = !on;
      }
      var doom = document.getElementById("beacon-tile");
      if (doom) {
        doom.hidden = !on;
      }
    }

    function setupEgg() {
      setRevealed(isFound());
      var egg = document.getElementById("launcher-egg");
      if (!egg || egg.getAttribute("data-wired") === "1") {
        return;
      }
      egg.setAttribute("data-wired", "1");
      egg.addEventListener("click", function () {
        // Tapping the glyph again hides them, and vice versa.
        var next = !revealed;
        try {
          if (next) {
            window.localStorage.setItem(KEY, "1");
          } else {
            window.localStorage.removeItem(KEY);
          }
        } catch (e) {
          /* storage unavailable; toggle for this page only */
        }
        if (next) {
          var storm = document.getElementById("packetstorm-tile");
          if (storm) {
            storm.classList.add("revealed");
          }
        }
        setRevealed(next);
      });
    }

    document.addEventListener("htmx:afterSwap", setupEgg);
    window.addEventListener("load", setupEgg);
    setupEgg();
  })();
})();
