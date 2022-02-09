function I(t) {
  return document.getElementById(t);
}
var userLang = navigator.language || navigator.userLanguage,
  trans = [[]];
function tr(t) {
  return void 0 !== trans[t][userLang] ? trans[t][userLang] : void 0 !== trans[t]["en-US"] ? trans[t]["en-US"] : "unknown translation";
}
function trw(t) {
  document.write(tr(t));
}
(trans.start = []),
  (trans.start["en-US"] = "START"),
  (trans.abort = []),
  (trans.abort["en-US"] = "ABORT"),
  (trans.response = []),
  (trans.response["en-US"] = "Response"),
  (trans.duration = []),
  (trans.duration["en-US"] = "Duration"),
  (trans.speed = []),
  (trans.speed["en-US"] = "Speed"),
  (trans.show_advanced = []),
  (trans.show_advanced["en-US"] = "SHOW ADVANCED"),
  (trans.settings = []),
  (trans.settings["en-US"] = "Settings"),
  (trans.stats = []),
  (trans.stats["en-US"] = "Stats"),
  (trans.test_length = []),
  (trans.test_length["en-US"] = "Test length:"),
  (trans.time = []),
  (trans.time["en-US"] = "Time"),
  (trans.speed = []),
  (trans.speed["en-US"] = "Speed"),
  (trans.ip_address = []),
  (trans.ip_address["en-US"] = "IP Address:"),
  (trans.maximal_download = []),
  (trans.maximal_download["en-US"] = "Maximal download:"),
  (trans.maximal_upload = []),
  (trans.maximal_upload["en-US"] = "Maximal upload:"),
  (trans.minimal_download = []),
  (trans.minimal_download["en-US"] = "Minimal download:"),
  (trans.minimal_upload = []),
  (trans.minimal_upload["en-US"] = "Minimal upload:"),
  (trans.total_download = []),
  (trans.total_download["en-US"] = "Total download:"),
  (trans.total_upload = []),
  (trans.total_upload["en-US"] = "Total upload:"),
  (trans.show_detailed_a = []),
  (trans.show_detailed_a["en-US"] = "Click here to show"),
  (trans.show_detailed_b = []),
  (trans.show_detailed_b["en-US"] = "detailed information about how <a href='https://github.com/librespeed/speedtest' target='_blank'>LibreSpeed</a> works and the algorithms involved."),
  (trans.desc_ping = []),
  (trans.desc_ping["en-US"] =
    "Ping is measured as a response time for a HTTP request. Multiple requests are sent in 100 ms intervals. The graph shows response times for individual requests. The time values are preferably obtained from the JavaScript Performance API. If this API is not supported in the user's web browser, the JavaScript Date().getTime() function is used, which however provides less precise values."),
  (trans.desc_jitter = []),
  (trans.desc_jitter["en-US"] = "Jitter is computed as a standard deviation of all ping values measured up to the given time. A more representative value is therefore indicated at the end of the measurement."),
  (trans.desc_down_up = []),
  (trans.desc_down_up["en-US"] =
    "Download and upload are measured by transferring blocks of data by HTTP requests. The bandwidth is computed from HTTP payload data transferred (without HTTP and lower layer headers). The graph shows an arithmetic mean of all values measured up to the given time. A more representative value for large file transfers is therefore indicated at the end of the measurement."),
  (trans.desc_final = []),
  (trans.desc_final["en-US"] = "The final number indicated in gauges is an average value for all pings and a value at the end of the measurement for the other characteristics."),
  (trans.desc_origin = []),
  (trans.desc_origin["en-US"] = "Original speedtest source code can be obtained at "),
  (trans.desc_questions = []),
  (trans.desc_questions["en-US"] = "For any questions regarding speedtest, please contact us on email: melnikov (at) cesnet.cz."),
  (trans.abort["cs-CZ"] = "Zrušit"),
  (trans.response["cs-CZ"] = "Odezva"),
  (trans.duration["cs-CZ"] = "Průběh"),
  (trans.show_advanced["cs-CZ"] = "Pokročilé nastavení"),
  (trans.settings["cs-CZ"] = "Nastavení"),
  (trans.test_length["cs-CZ"] = "Délka testu:"),
  (trans.stats["cs-CZ"] = "Statistiky"),
  (trans.time["cs-CZ"] = "Čas"),
  (trans.speed["cs-CZ"] = "Rychlost"),
  (trans.ip_address["cs-CZ"] = "IP Adresa:"),
  (trans.maximal_download["cs-CZ"] = "Maximální download:"),
  (trans.maximal_upload["cs-CZ"] = "Maximální upload:"),
  (trans.minimal_download["cs-CZ"] = "Minimální download:"),
  (trans.minimal_upload["cs-CZ"] = "Minimální upload:"),
  (trans.total_download["cs-CZ"] = "Celkový download:"),
  (trans.total_upload["cs-CZ"] = "Celkový upload:"),
  (trans.show_detailed_a["cs-CZ"] = "Zobrazit"),
  (trans.show_detailed_b["cs-CZ"] = "detailní informace o použitých algoritmech."),
  (trans.desc_ping["cs-CZ"] =
    "Ping je měřen jako čas odezvy na požadavek protokolu HTTP. Je odeslána řada požadavků v intervalu 100 ms. V grafu jsou zobrazeny časy odezvy na jednotlivé požadavky. Časové hodnoty jsou prioritně získávány z Javascript Performance API. Pokud toto rozhraní není ve Vašem webovém prohlížeči podporováno, je použita Javascript funkce Date().getTime(), která ale poskytuje méně přesné hodnoty."),
  (trans.desc_jitter["cs-CZ"] = "Jitter je počítán jako směrodatná odchylka všech naměřených hodnot pingu až do daného času. Reprezentativnější hodnota je tedy zobrazena na konci měření."),
  (trans.desc_down_up["cs-CZ"] =
    "Download a upload jsou měřeny přenosem bloků dat pomocí protokolu HTTP. Kapacita je počítána z přenesených uživatelských dat (bez hlaviček HTTP a hlaviček nižších vrstev). Graf zobrazuje aritmetický průměr všech hodnot naměřených až do daného času. Reprezentativnější hodnota pro přenosy velkých souborů je tedy zobrazena na konci měření."),
  (trans.desc_final["cs-CZ"] = "Konečné hodnoty uvedené uprostřed grafických indikátorů jsou průměrná hodnota pro všechny pingy a hodnota na konci měření pro ostatní charakteristiky."),
  (trans.desc_origin["cs-CZ"] = "Zdrojové kódy původního speedtestu jsou k dispozici na serveru ");
var chart1,
  chart2,
  last_chart_pos,
  meterBk = "#EAEAEA",
  dlColor = "#6060aa",
  ulColor = "#309030",
  pingColor = "#ffcc00",
  jitColor = "#cc0000",
  progColor = "#EEEEEE",
  w = null,
  sampling = !1,
  data = [],
  timers = [],
  parameters = { overheadCompensationFactor: 1, enable_quirks: !0, time_ul_max: 15, time_dl_max: 15, time_ulGraceTime: 3, time_dlGraceTime: 1.5, count_ping: 35, time_auto: !1 },
  max_upload = 0,
  min_upload = 0,
  max_download = 0,
  min_download = 0,
  total_upload = 0,
  total_download = 0,
  ping_sum = 0,
  ping_cnt = 0.001;
function drawMeter(t, a, e, r, o, n) {
  var s = t.getContext("2d"),
    d = window.devicePixelRatio || 1,
    i = t.clientWidth * d,
    l = t.clientHeight * d,
    p = 0.0055 * l;
  t.width == i && t.height == l ? s.clearRect(0, 0, i, l) : ((t.width = i), (t.height = l)),
    s.beginPath(),
    (s.strokeStyle = e),
    (s.lineWidth = 16 * p),
    s.arc(t.width / 2, t.height - 58 * p, t.height / 1.8 - s.lineWidth, 1.1 * -Math.PI, 0.1 * Math.PI),
    s.stroke(),
    s.beginPath(),
    (s.strokeStyle = r),
    (s.lineWidth = 16 * p),
    s.arc(t.width / 2, t.height - 58 * p, t.height / 1.8 - s.lineWidth, 1.1 * -Math.PI, a * Math.PI * 1.2 - 1.1 * Math.PI),
    s.stroke(),
    void 0 !== o && ((s.fillStyle = n), s.fillRect(0.3 * t.width, t.height - 16 * p, 0.4 * t.width * o, 4 * p));
}
function mbpsToAmount(t) {
  return 1 - 1 / Math.pow(1.3, Math.sqrt(t));
}
function msToAmount(t) {
  return 1 - 1 / Math.pow(1.08, Math.sqrt(t));
}
function oscillate() {
  return 1 + 0.02 * Math.sin(Date.now() / 100);
}
function initUI() {
  drawMeter(I("dl_meter"), 0, meterBk, dlColor, 0),
    drawMeter(I("ul_meter"), 0, meterBk, ulColor, 0),
    drawMeter(I("ping_meter"), 0, meterBk, pingColor, 0),
    drawMeter(I("jitter_meter"), 0, meterBk, jitColor, 0),
    (I("dl_text").textContent = ""),
    (I("ul_text").textContent = ""),
    (I("ping_text").textContent = ""),
    (I("jitter_text").textContent = "");
  var t = document.getElementById("chart_du_area").getContext("2d"),
    a = document.getElementById("chart_pj_area").getContext("2d"),
    e = {
      type: "line",
      data: {
        datasets: [
          {
            label: "Download",
            fill: !1,
            lineTension: 0.1,
            backgroundColor: "rgba(96,96,170,0.5)",
            borderColor: "rgba(96,96,170,1)",
            borderCapStyle: "butt",
            borderDash: [],
            borderDashOffset: 0,
            borderJoinStyle: "miter",
            pointBorderColor: "rgba(96,96,170,1)",
            pointBackgroundColor: "#fff",
            pointBorderWidth: 1,
            pointHoverRadius: 0,
            pointHoverBackgroundColor: "rgba(96,96,170,1)",
            pointHoverBorderColor: "rgba(220,220,220,1)",
            pointHoverBorderWidth: 2,
            pointRadius: 1,
            pointHitRadius: 10,
            data: [0],
            spanGaps: !1,
          },
          {
            label: "Upload",
            fill: !1,
            lineTension: 0.1,
            backgroundColor: "rgba(48,144,48,0.5)",
            borderColor: "rgba(48,144,48,1)",
            borderCapStyle: "butt",
            borderDash: [],
            borderDashOffset: 0,
            borderJoinStyle: "miter",
            pointBorderColor: "rgba(48,144,48,1)",
            pointBackgroundColor: "#fff",
            pointBorderWidth: 1,
            pointHoverRadius: 0,
            pointHoverBackgroundColor: "rgba(48,144,48,1)",
            pointHoverBorderColor: "rgba(220,220,220,1)",
            pointHoverBorderWidth: 2,
            pointRadius: 1,
            pointHitRadius: 10,
            data: [0],
            spanGaps: !1,
          },
        ],
      },
      options: {
        responsive: !0,
        tooltips: { enabled: !1 },
        legend: { position: "top" },
        scales: {
          xAxes: [{ display: !0, scaleLabel: { display: !0, labelString: tr("duration") + " (s)" }, ticks: { beginAtZero: !0 } }],
          yAxes: [{ display: !0, scaleLabel: { display: !0, labelString: tr("speed") + " (Mbps)" }, ticks: { beginAtZero: !0 } }],
        },
      },
    },
    r = {
      type: "line",
      data: {
        datasets: [
          {
            label: "Ping",
            fill: !1,
            lineTension: 0.1,
            backgroundColor: "rgba(255,204,0,0.5)",
            borderColor: "rgba(255,204,0,1)",
            borderCapStyle: "butt",
            borderDash: [],
            borderDashOffset: 0,
            borderJoinStyle: "miter",
            pointBorderColor: "rgba(255,204,0,1)",
            pointBackgroundColor: "#fff",
            pointBorderWidth: 1,
            pointHoverRadius: 0,
            pointHoverBackgroundColor: "rgba(75,220,75,1)",
            pointHoverBorderColor: "rgba(220,220,220,1)",
            pointHoverBorderWidth: 2,
            pointRadius: 1,
            pointHitRadius: 10,
            data: [],
            spanGaps: !1,
          },
          {
            label: "Jitter",
            fill: !1,
            lineTension: 0.1,
            backgroundColor: "rgba(204,0,0,0.5)",
            borderColor: "rgba(204,0,0,1)",
            borderCapStyle: "butt",
            borderDash: [],
            borderDashOffset: 0,
            borderJoinStyle: "miter",
            pointBorderColor: "rgba(204,0,0,1)",
            pointBackgroundColor: "#fff",
            pointBorderWidth: 1,
            pointHoverRadius: 0,
            pointHoverBackgroundColor: "rgba(220,75,75,1)",
            pointHoverBorderColor: "rgba(220,220,220,1)",
            pointHoverBorderWidth: 2,
            pointRadius: 1,
            pointHitRadius: 10,
            data: [],
            spanGaps: !1,
          },
        ],
      },
      options: {
        responsive: !0,
        tooltips: { enabled: !1 },
        legend: { position: "top" },
        scales: {
          xAxes: [{ display: !0, scaleLabel: { display: !0, labelString: tr("duration") + " (ms)" }, ticks: { beginAtZero: !0 } }],
          yAxes: [{ display: !0, scaleLabel: { display: !0, labelString: tr("response") + " (ms)" }, ticks: { beginAtZero: !0 } }],
        },
      },
    };
  void 0 !== chart1 && chart1.destroy(),
    void 0 !== chart2 && chart2.destroy(),
    (chart1 = new Chart(t, e)),
    (chart2 = new Chart(a, r)),
    $("#results_table_download").html("<tr><th>" + tr("time") + " (s)</th><th>" + tr("speed") + " (Mbps)</th></tr>"),
    $("#results_table_upload").html("<tr><th>" + tr("time") + " (s)</th><th>" + tr("speed") + " (Mbps)</th></tr>"),
    $("#stats_table").html(""),
    (max_download = 0),
    (min_download = 0),
    (max_upload = 0),
    (min_upload = 0),
    (total_download = 0),
    (total_upload = 0),
    $("#length").val(parameters.time_dl_max);
}
function updateUI(t) {
  if (t || (data && w)) {
    var a = Number(data[0]);
    if (
      ((I("dl_text").textContent = 1 == a && 0 == data[1] ? "..." : data[1]),
      drawMeter(I("dl_meter"), mbpsToAmount(Number(data[1] * (1 == a ? oscillate() : 1))), meterBk, dlColor, Number(data[6]), progColor),
      (I("ul_text").textContent = 3 == a && 0 == data[2] ? "..." : data[2]),
      drawMeter(I("ul_meter"), mbpsToAmount(Number(data[2] * (3 == a ? oscillate() : 1))), meterBk, ulColor, Number(data[7]), progColor),
      2 === a && Number(data[3]) > 0 && ((ping_sum += Number(data[3])), ping_cnt++),
      (I("ping_text").textContent = (ping_sum / ping_cnt).toFixed(2)),
      drawMeter(I("ping_meter"), msToAmount(Number((ping_sum / ping_cnt) * (2 == a ? oscillate() : 1))), meterBk, pingColor, Number(data[8]), progColor),
      (I("jitter_text").textContent = data[5]),
      drawMeter(I("jitter_meter"), msToAmount(Number(data[5] * (2 == a ? oscillate() : 1))), meterBk, jitColor, Number(data[8]), progColor),
      1 === a && Number(data[1]) > 0)
    ) {
      let t = ~~(parameters.time_dl_max * Number(data[6]));
      (chart1.data.datasets[0].data[t] = Number(data[1])),
        (chart1.data.labels[chart1.data.datasets[0].data.length - 1] = t),
        chart1.update(),
        last_chart_pos != t &&
          0 != t &&
          ($("#results_table_download").append("<tr><td>" + t + "</td><td>" + Number(data[1]) + "</td></tr>"),
          (Number(data[1]) > max_download || max_download <= 0) && (max_download = Number(data[1])),
          (Number(data[1]) < min_download || min_download <= 0) && (min_download = Number(data[1])),
          (total_download = data[9]),
          updateStats(),
          (last_chart_pos = t));
}
    if (3 === a && Number(data[2]) > 0) {
      let t = ~~(parameters.time_ul_max * Number(data[7]));
      (chart1.data.datasets[1].data[t] = Number(data[2])),
        (chart1.data.labels[chart1.data.datasets[1].data.length - 1] = t),
        chart1.update(),
        last_chart_pos != t &&
          0 != t &&
          ($("#results_table_upload").append("<tr><td>" + t + "</td><td>" + Number(data[2]) + "</td></tr>"),
          (last_chart_pos = t),
          (Number(data[1]) > max_upload || max_upload <= 0) && (max_upload = Number(data[2])),
          (Number(data[1]) < min_upload || min_upload <= 0) && (min_upload = Number(data[2])),
          (total_upload = data[10]),
          updateStats());
    }
    2 === a &&
      Number(data[3]) > 0 &&
      (chart2.data.datasets[0].data.push(Number(data[3])),
      chart2.data.datasets[1].data.push(Number(data[5])),
      (chart2.data.labels[chart2.data.datasets[0].data.length - 1] = ""),
      (chart2.data.labels[chart2.data.datasets[1].data.length - 1] = 100 * Math.round(data[11] / 100)),
      chart2.update());
  }
}
function updateStats() {
  $("#stats_table").html(
    "        <tr><th>" +
      tr("minimal_download") +
      "</th><td>" +
      min_download +
      " Mbps</td></tr>        <tr><th>" +
      tr("maximal_download") +
      "</th><td>" +
      max_download +
      " Mbps</td></tr>        <tr><th>" +
      tr("minimal_upload") +
      "</th><td>" +
      min_upload +
      " Mbps</td></tr>        <tr><th>" +
      tr("maximal_upload") +
      "</th><td>" +
      max_upload +
      " Mbps</td></tr>        <tr><th>" +
      tr("total_download") +
      "</th><td>" +
      Math.round(total_download / 1024 / 1024) +
      " MB</td></tr>        <tr><th>" +
      tr("total_upload") +
      "</th><td>" +
      Math.round(total_upload / 1024 / 1024) +
      " MB</td></tr>        "
  );
}
function startStop() {
  if (null != w) w.postMessage("abort"), resetUI(), initUI();
  else {
    let t = parseInt($("#length").attr("min")),
      a = parseInt($("#length").attr("max")),
      e = parseInt($("#length").val());
    e < t && (e = t),
      e > a && (e = a),
      (parameters.time_dl_max = e),
      (parameters.time_ul_max = e),
      initUI(),
      (w = new Worker("speedtest_worker.js")).postMessage("start " + JSON.stringify(parameters)),
      (I("startStopBtn").className = "btn disabled"),
      (I("startStopBtn").innerHTML = tr("abort")),
      setTimeout(function () {
        I("startStopBtn").className = "btn running";
      }, 1500),
      (w.onmessage = function (t) {
        var a = JSON.parse(t.data);
        (data[0] = a.testState),
          (data[1] = a.dlStatus),
          (data[2] = a.ulStatus),
          (data[3] = a.pingStatus),
          (data[4] = a.clientIp),
          (data[5] = a.jitterStatus),
          (data[6] = a.dlProgress),
          (data[7] = a.ulProgress),
          (data[8] = a.pingProgress),
          (data[9] = a.dlAmount),
          (data[10] = a.ulAmount);
        var e = a.testState;
        null == timers[1] && 1 == e && (timers[1] = performance.now()),
          null == timers[2] && 2 == e && (timers[2] = performance.now()),
          null == timers[3] && 3 == e && (timers[3] = performance.now()),
          e >= 4 ? (resetUI(), updateUI(!0)) : ((data[11] = performance.now() - timers[e]), updateUI()),
          setTimeout(function () {
            null != w && w.postMessage("status");
          }, 50);
      }),
      w.postMessage("status");
  }
}
function resetUI() {
  (I("startStopBtn").className = "btn"), (I("startStopBtn").innerHTML = tr("start")), (w = null), (sampling = !1), delete timers[1], delete timers[2], delete timers[3];
}
$(document).ready(function () {
  $("#show_advanced").click(function () {
    $("#advanced").slideToggle(300);
  }),
    $("#show_speedtest_info").click(function () {
      $("#speedtest_info").slideToggle(300);
    });
}),
  window.addEventListener(
    "focus",
    function (t) {
      data || (data = ["0", "", "", "", "", "", "0", "0", "0", 0]), updateUI(!0), chart1.update(), chart2.update();
    },
    !1
  );

