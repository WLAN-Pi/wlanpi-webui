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

  function applyWidths(tbl, widths) {
    headerCells(tbl).forEach(function (th) {
      var width = widths[th.dataset.column] || "";
      th.style.width = width;
      th.style.maxWidth = width;
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

  function attachResizers(tbl) {
    headerCells(tbl).forEach(function (th) {
      if (th.querySelector(".cap-resizer")) return;
      var resizer = document.createElement("div");
      resizer.className = "cap-resizer";
      th.appendChild(resizer);
      var startX = 0;
      var startWidth = 0;
      function onMove(evt) {
        var width = Math.max(48, startWidth + (evt.clientX - startX));
        th.style.width = width + "px";
        th.style.maxWidth = width + "px";
      }
      function onUp() {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        var stored = readJSON(WIDTHS_KEY, {}) || {};
        stored[th.dataset.column] = th.style.width;
        writeJSON(WIDTHS_KEY, stored);
      }
      resizer.addEventListener("mousedown", function (evt) {
        evt.preventDefault();
        evt.stopPropagation();
        startX = evt.clientX;
        startWidth = th.offsetWidth;
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
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

  document.addEventListener("htmx:afterSwap", function () {
    checkNewProfile();
    init();
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
