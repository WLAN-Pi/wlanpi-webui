// Latency history: samples the Reachability card after every cards refresh
// and draws ping google / ping gateway / arping on one graph. Chart.js is
// lazy-loaded so the 200 KB bundle never blocks the page, the colours come
// from the theme tokens, and the axes use a fixed five-minute window and a
// grow-only y-max so the graph does not rescale as samples arrive.
(function () {
  if (window.wlanpiLatencyInit) return;
  window.wlanpiLatencyInit = true;

  var KEY = "wlanpi-latency";
  var MAX = 120;
  var WINDOW = 5 * 60 * 1000;
  // The versioned URL comes from the template (see network.html).
  var script = document.currentScript;
  var chartUrl =
    (script && script.dataset.chartSrc) || "/static/js/Chart.bundle.min.js";
  var axisMax = 0;
  var sampled = false;
  var REDUCED = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  function loadChart(cb) {
    if (window.Chart) { cb(); return; }
    var s = document.getElementById("chartjs-loader");
    if (s) { s.addEventListener("load", cb, { once: true }); return; }
    s = document.createElement("script");
    s.id = "chartjs-loader";
    s.src = chartUrl;
    s.onload = cb;
    document.head.appendChild(s);
  }

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return []; }
  }

  function save(hist) {
    try { localStorage.setItem(KEY, JSON.stringify(hist.slice(-MAX))); } catch (e) { /* ignore */ }
  }

  function parseVal(text, label) {
    var m = text.match(new RegExp(label + ":\\s*([0-9.]+)\\s*ms"));
    return m ? parseFloat(m[1]) : null;
  }

  function cssVar(name, fallback) {
    try {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name);
      return (v && v.trim()) || fallback;
    } catch (e) { return fallback; }
  }

  function colors() {
    return {
      text: cssVar("--text-muted", "#888"),
      grid: cssVar("--border", "rgba(128,128,128,0.25)"),
      brand: cssVar("--brand", "#f45625"),
      info: cssVar("--info", "#0277bd"),
      success: cssVar("--success", "#2e7d32")
    };
  }

  function history() {
    var cutoff = Date.now() - WINDOW;
    return load().filter(function (p) { return p.t >= cutoff; });
  }

  var GAP_MS = 120 * 1000;

  // Build a series, inserting a null break whenever samples are missing for
  // a stretch of time, so the line never spans a gap where there is no data.
  function seriesData(hist, key) {
    var out = [];
    var prev = null;
    hist.forEach(function (p) {
      if (prev !== null && p.t - prev.t > GAP_MS) {
        out.push({ x: prev.t + (p.t - prev.t) / 2, y: null });
      }
      out.push({ x: p.t, y: p[key] });
      prev = p;
    });
    return out;
  }

  function dataset(hist, key, label, color, pointRadius) {
    return {
      label: label,
      data: seriesData(hist, key),
      fill: false,
      lineTension: 0.1,
      borderColor: color,
      backgroundColor: color,
      pointRadius: pointRadius,
      spanGaps: false
    };
  }

  function dataFor(hist, c) {
    // Dots while the window is sparse, so the first sample is visible.
    var pr = hist.length <= 8 ? 2 : 0;
    return {
      datasets: [
        dataset(hist, "g", "Ping Google", c.brand, pr),
        dataset(hist, "gw", "Ping Gateway", c.info, pr),
        dataset(hist, "arp", "Arping Gateway", c.success, pr)
      ]
    };
  }

  // Round up to a tidy ceiling that only ever grows, so the y-axis is stable.
  function updateAxisMax(hist) {
    var m = 0;
    hist.forEach(function (p) {
      if (p.g != null && p.g > m) { m = p.g; }
      if (p.gw != null && p.gw > m) { m = p.gw; }
      if (p.arp != null && p.arp > m) { m = p.arp; }
    });
    var nice = Math.max(20, Math.ceil(m / 10) * 10);
    if (nice > axisMax) {
      axisMax = nice;
    }
  }

  function options(c, tMin, tMax) {
    var narrow = window.innerWidth < 640;
    return {
      type: "line",
      data: { datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: REDUCED ? 0 : 300 },
        legend: {
          position: narrow ? "bottom" : "top",
          labels: { fontColor: c.text, fontSize: narrow ? 10 : 12, boxWidth: narrow ? 10 : 12 }
        },
        scales: {
          xAxes: [{
            type: "time",
            time: {
              min: tMin,
              max: tMax,
              displayFormats: { second: "HH:mm:ss", minute: "HH:mm" }
            },
            gridLines: { color: c.grid },
            ticks: { fontColor: c.text, maxTicksLimit: narrow ? 4 : 8, fontSize: narrow ? 9 : 11 }
          }],
          yAxes: [{
            gridLines: { color: c.grid },
            ticks: {
              fontColor: c.text,
              beginAtZero: true,
              max: axisMax || undefined,
              fontSize: narrow ? 9 : 11
            },
            scaleLabel: { display: !narrow, labelString: "ms", fontColor: c.text }
          }]
        }
      }
    };
  }

  function render() {
    var canvas = document.getElementById("latency-chart");
    if (!canvas || !window.Chart) return;
    var skeleton = document.getElementById("latency-skeleton");
    var empty = document.getElementById("latency-empty");
    var hist = history();
    var points = hist.filter(function (p) {
      return p.g != null || p.gw != null || p.arp != null;
    }).length;

    if (skeleton) { skeleton.hidden = sampled; }
    if (empty) { empty.hidden = points >= 1; }
    if (points < 1) {
      canvas.style.visibility = "hidden";
      return;
    }
    canvas.style.visibility = "visible";

    var c = colors();
    var now = Date.now();
    var tMin = now - WINDOW;
    updateAxisMax(hist);

    if (!window.wlanpiLatencyChart || !canvas.dataset.live) {
      if (window.wlanpiLatencyChart) { window.wlanpiLatencyChart.destroy(); }
      var opts = options(c, tMin, now);
      opts.data = dataFor(hist, c);
      window.wlanpiLatencyChart = new Chart(canvas.getContext("2d"), opts);
      canvas.dataset.live = "1";
    } else {
      var ch = window.wlanpiLatencyChart;
      ch.data.datasets = dataFor(hist, c).datasets;
      ch.options.scales.xAxes[0].time.min = tMin;
      ch.options.scales.xAxes[0].time.max = now;
      ch.options.scales.xAxes[0].ticks.fontColor = c.text;
      ch.options.scales.xAxes[0].gridLines.color = c.grid;
      ch.options.scales.yAxes[0].ticks.fontColor = c.text;
      ch.options.scales.yAxes[0].ticks.max = axisMax;
      ch.options.scales.yAxes[0].gridLines.color = c.grid;
      ch.options.scales.yAxes[0].scaleLabel.fontColor = c.text;
      ch.options.legend.labels.fontColor = c.text;
      ch.update();
    }
  }

  function sample() {
    var card = document.getElementById("reachability");
    if (!card) return;
    var text = card.innerText;
    var hist = load();
    hist.push({
      t: Date.now(),
      g: parseVal(text, "Ping Google"),
      gw: parseVal(text, "Ping Gateway"),
      arp: parseVal(text, "Arping Gateway")
    });
    save(hist);
    sampled = true;
    render();
  }

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.detail && evt.detail.target && evt.detail.target.id === "network-cards") {
      sample();
    }
  });

  // An unchanged poll comes back 204 and doesn't swap; the readings on the
  // page are still current, so record them.
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    var d = evt.detail;
    if (d && d.xhr && d.xhr.status === 204 && d.target && d.target.id === "network-cards") {
      sample();
    }
  });

  // Follow the theme: re-read the tokens when it flips.
  try {
    new MutationObserver(render).observe(document.documentElement, {
      attributes: true, attributeFilter: ["data-theme"]
    });
  } catch (e) { /* ignore */ }

  // Loaded after the first cards swap (htmx navigation): take that sample now.
  if (document.getElementById("reachability")) sample();

  loadChart(render);
  render();
})();
