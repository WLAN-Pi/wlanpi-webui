/* WLAN Pi WebUI: theme toggle, toast helper and session-expiry handling. */
(function () {
  "use strict";

  // ---- Theme ----------------------------------------------------------
  // The stored preference is applied here, before the stylesheets are
  // evaluated, so there is no flash of the wrong theme.
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("wlanpi-theme", theme);
    } catch (e) {
      /* storage unavailable; keep the in-page theme only */
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
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {
    /* ignore */
  }

  // ---- Toasts ---------------------------------------------------------
  window.wlanpiToast = function (message, status) {
    if (window.UIkit && UIkit.notification) {
      UIkit.notification({
        message: message,
        status: status || "primary",
        pos: "top-right",
        timeout: 10000,
      });
    }
  };

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
})();
