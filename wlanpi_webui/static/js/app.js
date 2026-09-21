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
  }

  window.wlanpiToggleTheme = function () {
    var current =
      document.documentElement.getAttribute("data-theme") === "dark"
        ? "dark"
        : "light";
    applyTheme(current === "dark" ? "light" : "dark");
  };

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

  // ---- Toasts and notification history --------------------------------
  // Persisted in localStorage but keyed by the kernel boot id, so it
  // survives reloads and clears on device reboot. The /notifications page
  // renders the list with a fuzzy search.
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
        (query ? "No matching notifications." : "No notifications yet.") +
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

  document.addEventListener("htmx:afterSwap", function () {
    renderNotifications();
  });
  window.addEventListener("load", function () {
    renderNotifications();
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
