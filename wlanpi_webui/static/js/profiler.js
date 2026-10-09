(function () {
  var COLS_KEY = "profiler:cols";
  var WIDTHS_KEY = "profiler:widths";

  function readJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  function writeJSON(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      /* storage unavailable: preferences are best-effort */
    }
  }

  function headerCells(tbl) {
    return Array.prototype.slice.call(
      tbl.querySelectorAll("thead th[data-column]")
    );
  }

  function allKeys(tbl) {
    return headerCells(tbl).map(function (th) {
      return th.dataset.column;
    });
  }

  function visibleKeys(tbl) {
    var stored = readJSON(COLS_KEY, null);
    var cells = headerCells(tbl);
    if (Array.isArray(stored)) {
      return allKeys(tbl).filter(function (key) {
        return stored.indexOf(key) !== -1;
      });
    }
    return cells
      .filter(function (th) {
        return th.dataset.default === "1";
      })
      .map(function (th) {
        return th.dataset.column;
      });
  }

  function applyVisibility(tbl, keys) {
    var visible = {};
    keys.forEach(function (key) {
      visible[key] = true;
    });
    headerCells(tbl).forEach(function (th) {
      var index = th.cellIndex;
      var show = !!visible[th.dataset.column];
      th.classList.toggle("cap-col-hidden", !show);
      tbl.querySelectorAll("tbody tr").forEach(function (row) {
        var td = row.cells[index];
        if (td) td.classList.toggle("cap-col-hidden", !show);
      });
    });
  }

  // An auto-layout table ignores a cell's width once it overflows its box;
  // min-width is what actually grows the column.
  function sizeColumn(th, width) {
    th.style.width = width;
    th.style.minWidth = width;
    th.style.maxWidth = width;
  }

  function clampWidth(width) {
    return Math.min(800, Math.max(48, Math.round(width)));
  }

  function applyWidths(tbl, widths) {
    headerCells(tbl).forEach(function (th) {
      var stored = parseFloat(widths[th.dataset.column]);
      sizeColumn(th, stored ? clampWidth(stored) + "px" : "");
    });
  }

  function buildPicker(tbl) {
    var picker = document.getElementById("cap-column-picker");
    if (!picker) return;
    var keys = visibleKeys(tbl);
    picker.innerHTML = "";
    headerCells(tbl).forEach(function (th) {
      var key = th.dataset.column;
      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = "checkbox";
      input.value = key;
      input.checked = keys.indexOf(key) !== -1;
      input.addEventListener("change", function () {
        var current = visibleKeys(tbl);
        if (input.checked) {
          if (current.indexOf(key) === -1) current.push(key);
        } else {
          current = current.filter(function (k) {
            return k !== key;
          });
        }
        if (current.length === 0) {
          input.checked = true;
          return;
        }
        var ordered = allKeys(tbl).filter(function (k) {
          return current.indexOf(k) !== -1;
        });
        writeJSON(COLS_KEY, ordered);
        applyVisibility(tbl, ordered);
      });
      var labelText = th.querySelector(".cap-th-label");
      var span = document.createElement("span");
      span.textContent = labelText ? labelText.textContent : key;
      label.appendChild(input);
      label.appendChild(span);
      picker.appendChild(label);
    });
  }

  // Drag (mouse, pen or touch) or arrow keys resize a column; the width is
  // remembered per column.
  function attachResizers(tbl) {
    headerCells(tbl).forEach(function (th) {
      if (th.querySelector(".cap-resizer")) return;
      var labelEl = th.querySelector(".cap-th-label");
      var resizer = document.createElement("div");
      resizer.className = "cap-resizer";
      resizer.tabIndex = 0;
      resizer.setAttribute("role", "separator");
      resizer.setAttribute("aria-orientation", "vertical");
      resizer.setAttribute("aria-valuemin", "48");
      resizer.setAttribute("aria-valuemax", "800");
      resizer.setAttribute(
        "aria-label",
        "Resize " + (labelEl ? labelEl.textContent : th.dataset.column) + " column"
      );
      th.appendChild(resizer);
      resizer.setAttribute(
        "aria-valuenow",
        String(Math.max(48, parseFloat(th.style.width) || th.offsetWidth))
      );
      var startX = 0;
      var startWidth = 0;

      function setWidth(width) {
        width = clampWidth(width);
        sizeColumn(th, width + "px");
        resizer.setAttribute("aria-valuenow", String(width));
      }

      function save() {
        var stored = readJSON(WIDTHS_KEY, {}) || {};
        stored[th.dataset.column] = th.style.width;
        writeJSON(WIDTHS_KEY, stored);
      }

      resizer.addEventListener("pointerdown", function (evt) {
        evt.preventDefault();
        evt.stopPropagation();
        startX = evt.clientX;
        startWidth = th.offsetWidth;
        resizer.setPointerCapture(evt.pointerId);
      });
      resizer.addEventListener("pointermove", function (evt) {
        if (!resizer.hasPointerCapture(evt.pointerId)) return;
        setWidth(startWidth + (evt.clientX - startX));
      });
      function endDrag(evt) {
        if (!resizer.hasPointerCapture(evt.pointerId)) return;
        resizer.releasePointerCapture(evt.pointerId);
        save();
      }
      resizer.addEventListener("pointerup", endDrag);
      resizer.addEventListener("pointercancel", endDrag);
      resizer.addEventListener("keydown", function (evt) {
        var step = evt.shiftKey ? 48 : 16;
        var delta =
          evt.key === "ArrowRight" ? step : evt.key === "ArrowLeft" ? -step : 0;
        if (!delta) return;
        evt.preventDefault();
        // From the set width, not offsetWidth: a cell can't shrink below its
        // content, and each press must still move the value.
        setWidth((parseFloat(th.style.width) || th.offsetWidth) + delta);
        save();
      });
      resizer.addEventListener("click", function (evt) {
        evt.preventDefault();
        evt.stopPropagation();
      });
    });
  }

  function clearHighlight(tbl) {
    tbl
      .querySelectorAll(".cap-hl-col, .cap-hl-cell")
      .forEach(function (el) {
        el.classList.remove("cap-hl-col", "cap-hl-cell");
      });
  }

  function attachCrossHighlight(tbl) {
    if (tbl.dataset.capHighlight === "1") return;
    tbl.dataset.capHighlight = "1";
    tbl.addEventListener("mouseover", function (evt) {
      var cell = evt.target.closest("td");
      if (!cell) return;
      clearHighlight(tbl);
      cell.classList.add("cap-hl-cell");
      var index = cell.cellIndex;
      tbl.querySelectorAll("tbody tr").forEach(function (row) {
        var other = row.cells[index];
        if (other && other !== cell) other.classList.add("cap-hl-col");
      });
    });
    tbl.addEventListener("mouseleave", function () {
      clearHighlight(tbl);
    });
  }

  window.wlanpiRenderQr = function (el) {
    if (!el || !window.QRCode) return;
    var spec = el.getAttribute("data-wifi") || "";
    if (!spec || el.dataset.rendered === spec) return;
    el.innerHTML = "";
    new QRCode(el, {
      text: spec,
      width: 148,
      height: 148,
      correctLevel: QRCode.CorrectLevel.M,
    });
    el.dataset.rendered = spec;
  };

  function renderQr() {
    var el = document.getElementById("profiler-qr");
    if (el) window.wlanpiRenderQr(el);
  }

  // The sticky MAC column sits to the right of the sticky actions column, so
  // its left offset has to track the actions column width.
  function syncStickyOffsets(tbl) {
    var actions = tbl.querySelector("thead .cap-sticky-actions");
    if (actions) {
      tbl.style.setProperty("--cap-actions-w", actions.offsetWidth + "px");
    }
  }

  var lastProfileCount = null;
  var lastProfileMac = "";

  // The session poll carries the profiler's profile counter. A rise means a
  // client was just profiled, so toast it (this also lands in the
  // notification history) and remember it for the row highlight.
  function checkNewProfile() {
    var el = document.getElementById("profiler-session-events");
    if (!el) {
      lastProfileCount = null;
      return;
    }
    var count = parseInt(el.dataset.profileCount || "0", 10);
    var mac = el.dataset.lastProfile || "";
    if (lastProfileCount !== null && count > lastProfileCount) {
      var delta = count - lastProfileCount;
      if (mac && window.wlanpiToast) {
        window.wlanpiToast(
          delta === 1
            ? "New client profiled: " + mac
            : delta + " new clients profiled (latest " + mac + ")",
          "success"
        );
      }
    }
    lastProfileCount = count;
    if (mac) lastProfileMac = mac;
  }

  // Highlight the most recently profiled client's row so it is obvious which
  // one just appeared. Re-applied after every table swap.
  function markNewRow() {
    var tbl = document.getElementById("cap-table");
    if (!tbl) return;
    tbl.querySelectorAll("tbody tr").forEach(function (tr) {
      tr.classList.toggle(
        "cap-row-new",
        !!lastProfileMac && tr.dataset.mac === lastProfileMac
      );
    });
  }

  function init() {
    renderQr();
    var tbl = document.getElementById("cap-table");
    if (!tbl) return;
    var keys = visibleKeys(tbl);
    applyVisibility(tbl, keys);
    applyWidths(tbl, readJSON(WIDTHS_KEY, {}) || {});
    buildPicker(tbl);
    attachResizers(tbl);
    attachCrossHighlight(tbl);
    syncStickyOffsets(tbl);
    markNewRow();
  }

  document.addEventListener("click", function (evt) {
    var copyBtn = evt.target.closest(".cap-copy");
    if (copyBtn) {
      var data = copyBtn.getAttribute("data-pcapng");
      if (data && window.wlanpiCopyText) {
        window.wlanpiCopyText(
          'echo "' + data + '" | base64 -d | wireshark -k -i -',
          copyBtn,
          "Wireshark command"
        );
      }
      return;
    }
    if (evt.target.closest("[data-cap-reset]")) {
      try {
        localStorage.removeItem(COLS_KEY);
        localStorage.removeItem(WIDTHS_KEY);
      } catch (e) {
        /* ignore */
      }
      init();
    }
  });

  // A report arrives as modal markup; open it, and on close drop it and hand
  // focus back to the button that asked for it (re-found by its request URL,
  // since the 5s table refresh may have replaced it meanwhile).
  function openReport(evt) {
    var t = evt.detail && evt.detail.target;
    if (!t || t.id !== "profiler-modals" || !window.UIkit) return;
    var modal = t.querySelector("[data-report-modal]");
    if (!modal) return;
    var opener = evt.detail.requestConfig && evt.detail.requestConfig.elt;
    var url = opener && opener.getAttribute("hx-get");
    modal.addEventListener("hidden", function onHidden(e) {
      if (e.target !== modal) return;
      modal.removeEventListener("hidden", onHidden);
      // After UIkit's own hidden handlers, which still guard focus until then.
      setTimeout(function () {
        window.UIkit.modal(modal).$destroy(true);
        var back = url && document.querySelector('[hx-get="' + CSS.escape(url) + '"]');
        if (back) back.focus();
      });
    });
    window.UIkit.modal(modal).show();
  }

  document.addEventListener("htmx:afterSwap", function (evt) {
    openReport(evt);
    checkNewProfile();
    init();
  });
  // UIkit moved an open report to <body>, so Back would snapshot it into
  // history and Forward would restore a dead overlay. Drop it first.
  document.addEventListener("htmx:beforeHistorySave", function () {
    document.querySelectorAll("[data-report-modal]").forEach(function (m) {
      m.remove();
    });
  });
  // The session poll re-sends the QR slot every 5s. Keep the drawn code when
  // the network is unchanged instead of redrawing (and flashing) it.
  document.addEventListener("htmx:oobBeforeSwap", function (evt) {
    if (evt.detail.target.id !== "profiler-qr-slot") return;
    var next = evt.detail.fragment.querySelector("#profiler-qr");
    var cur = document.getElementById("profiler-qr");
    if (next && cur && next.dataset.wifi === cur.dataset.rendered) {
      evt.detail.shouldSwap = false;
    }
  });
  // The QR slot arrives out-of-band with the session poll; draw it on arrival.
  document.addEventListener("htmx:load", function (evt) {
    var el = evt.detail && evt.detail.elt;
    if (!el || !el.querySelector) return;
    var qr = el.id === "profiler-qr" ? el : el.querySelector("#profiler-qr");
    if (qr) window.wlanpiRenderQr(qr);
  });
  window.addEventListener("load", function () {
    checkNewProfile();
    init();
  });
  window.addEventListener("resize", function () {
    var tbl = document.getElementById("cap-table");
    if (tbl) syncStickyOffsets(tbl);
  });
})();
