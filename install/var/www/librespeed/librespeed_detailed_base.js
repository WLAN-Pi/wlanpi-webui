// credit: https://speedtest.cesnet.cz/speedtest_base.js?v=1.4

function I(id) {
    return document.getElementById(id);
}

var userLang = navigator.language || navigator.userLanguage,
    trans = [
        []
    ];

function tr(t) {
    return void 0 !== trans[t][userLang] ? trans[t][userLang] : void 0 !== trans[t]["en-US"] ? trans[t]["en-US"] : "unknown translation";
}

function trw(t) {
    document.write(tr(t));
}
(trans.start = []),
(trans.start["en-US"] = "START"),
(trans.abort = []),
(trans.abort["en-US"] = "STOP"),
(trans.response = []),
(trans.response["en-US"] = "Response"),
(trans.duration = []),
(trans.duration["en-US"] = "Duration"),
(trans.speed = []),
(trans.speed["en-US"] = "Speed"),
(trans.settings = []),
(trans.settings["en-US"] = "Settings"),
(trans.stats = []),
(trans.stats["en-US"] = "Statistics"),
(trans.test_length = []),
(trans.test_length["en-US"] = "Test length:"),
(trans.time = []),
(trans.time["en-US"] = "Time"),
(trans.speed = []),
(trans.speed["en-US"] = "Speed"),
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
(trans.desc_ping = []),
(trans.desc_ping["en-US"] =
    "Ping is measured as a response time for an HTTP request. Multiple requests are sent in 100 ms intervals. The graph shows response times for individual requests. The time values are preferably obtained from the JavaScript Performance API. If this API is not supported in the user's web browser, the JavaScript Date().getTime() function is used, which provides less precise values."),
(trans.desc_jitter = []),
(trans.desc_jitter["en-US"] = "Jitter is computed as the standard deviation of all ping values measured up to the given time. A more representative value is therefore indicated at the end of the measurement."),
(trans.desc_down_up = []),
(trans.desc_down_up["en-US"] =
    "Download and upload are measured by transferring blocks of data via HTTP requests. The bandwidth is computed from HTTP payload data transferred (without HTTP and lower-layer headers). The graph shows an arithmetic mean of all values measured up to the given time. A more representative value for large file transfers is therefore indicated at the end of the measurement."),
(trans.desc_final = []),
(trans.desc_final["en-US"] = "The final number indicated in gauges is an average value for all pings and a value at the end of the measurement for the other characteristics."),
(trans.desc_origin = []),
(trans.desc_origin["en-US"] = "Original speedtest source code can be obtained at "),
(trans.desc_questions = []),
(trans.desc_questions["en-US"] = "For any questions regarding speedtest, please don't contact us.");
var chart1,
    chart2,
    last_chart_pos,
    meterBk = "#dadada",
    dlColor = "#6060aa",
    ulColor = "#309030",
    pingColor = "#b8860b",
    jitColor = "#cc0000",
    progColor = "#EEEEEE",
    surfaceColor = "#ffffff",
    textColor = "#222222",
    w = null,
    sampling = false,
    data = [],
    timers = [],
    parameters = {
        overheadCompensationFactor: 1.0, // 1 = raw performance
        mpot: false,
        forceIE11Workaround: false,
        test_order: 'P_D_U',
        time_ul_max: 15,
        time_dl_max: 15,
        time_ulGraceTime: 3,
        time_dlGraceTime: 1.5,
        time_auto: false,
        count_ping: 100,
        enable_quirks: true,
        url_dl: "data/garbage.dat",
        url_ul: "data/empty.dat",
        url_ping: "data/empty.dat",
        url_getIp: "getip",
        getIp_ispInfo: false
    },
    max_upload = 0,
    min_upload = 0,
    max_download = 0,
    min_download = 0,
    total_upload = 0,
    total_download = 0,
    dl_samples = [],
    ul_samples = [],
    last_loaded_ping = null,
    last_loaded_jitter = null,
    unloaded_jitter = null,
    ping_sum = 0,
    ping_cnt = 0.001;


// Read meter and chart colours from the theme tokens so the page follows the
// WebUI light/dark theme (the HTML sets data-theme before this runs).
function applyMeterTheme() {
    try {
        var cs = getComputedStyle(document.documentElement);
        var get = function (name, fallback) {
            var v = cs.getPropertyValue(name);
            return (v && v.trim()) || fallback;
        };
        meterBk = get("--ls-meter-bg", meterBk);
        progColor = get("--ls-meter-progress", progColor);
        dlColor = get("--ls-dl", dlColor);
        ulColor = get("--ls-ul", ulColor);
        pingColor = get("--ls-ping", pingColor);
        jitColor = get("--ls-jitter", jitColor);
        surfaceColor = get("--bg-surface", surfaceColor);
        textColor = get("--text", textColor);
        if (window.Chart) {
            Chart.defaults.global.defaultFontColor = get("--text-muted", "#666");
            if (Chart.defaults.scale && Chart.defaults.scale.gridLines) {
                Chart.defaults.scale.gridLines.color = get("--border", "rgba(0,0,0,0.1)");
            }
        }
    } catch (e) { /* keep defaults */ }
}
applyMeterTheme();

function applyLiveTheme(theme) {
    if (theme !== "dark" && theme !== "light") return;
    document.documentElement.setAttribute("data-theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0b0f13" : "#f8f8f8");
    applyMeterTheme();

    [[chart1, [dlColor, ulColor]], [chart2, [pingColor, jitColor]]].forEach(function (entry) {
        var chart = entry[0];
        if (!chart) return;
        chart.data.datasets.forEach(function (dataset, i) {
            var color = entry[1][i];
            dataset.backgroundColor = alpha(color, 0.5);
            dataset.borderColor = color;
            dataset.pointBorderColor = color;
            dataset.pointBackgroundColor = surfaceColor;
            dataset.pointHoverBackgroundColor = color;
            dataset.pointHoverBorderColor = surfaceColor;
        });
        chart.options.legend.labels.fontColor = textColor;
        chart.options.scales.xAxes.concat(chart.options.scales.yAxes).forEach(function (axis) {
            axis.ticks.fontColor = textColor;
            axis.gridLines = axis.gridLines || {};
            axis.gridLines.color = getComputedStyle(document.documentElement).getPropertyValue("--border").trim();
            axis.scaleLabel.fontColor = textColor;
        });
    });

    if (data) updateUI(true);
    if (chart1) chart1.update();
    if (chart2) chart2.update();
}


function alpha(color, a) {
    var h = String(color).trim().replace("#", "");
    if (h.length === 3) { h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]; }
    var n = parseInt(h, 16);
    if (h.length !== 6 || isNaN(n)) { return color; }
    return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
}

function drawMeter(c, amount, bk, fg, progress, prog) {
    // Remember how to redraw this meter: a resize or a device pixel ratio
    // change (dragging the window to another display) would otherwise leave a
    // stale canvas until the next sample arrives.
    c.redraw = function () { drawMeter(c, amount, bk, fg, progress, prog); };
    var ctx = c.getContext("2d");
    var dp = window.devicePixelRatio || 1;
    // Round: c.width is an integer, so a fractional comparison would resize
    // (and clear) the canvas on every single draw.
    var cw = Math.round(c.clientWidth * dp),
        ch = Math.round(c.clientHeight * dp);
    var sizScale = ch * 0.0055;
    if (c.width === cw && c.height === ch) {
        ctx.clearRect(0, 0, cw, ch);
    } else {
        c.width = cw;
        c.height = ch;
    }
    ctx.beginPath();
    ctx.strokeStyle = bk;
    ctx.lineWidth = 16 * sizScale;
    ctx.arc(c.width / 2, c.height - 58 * sizScale, c.height / 1.8 - ctx.lineWidth, -Math.PI * 1.1, Math.PI * 0.1);
    ctx.stroke();
    ctx.beginPath();
    ctx.strokeStyle = fg;
    ctx.lineWidth = 16 * sizScale;
    ctx.arc(c.width / 2, c.height - 58 * sizScale, c.height / 1.8 - ctx.lineWidth, -Math.PI * 1.1, amount * Math.PI * 1.2 - Math.PI * 1.1);
    ctx.stroke();
    if (typeof progress !== "undefined") {
        ctx.fillStyle = prog;
        ctx.fillRect(c.width * 0.3, c.height - 16 * sizScale, c.width * 0.4 * progress, 4 * sizScale);
    }
}

window.addEventListener("resize", function () {
    ["dl_meter", "ul_meter", "ping_meter", "jitter_meter"].forEach(function (id) {
        var c = I(id);
        if (c && c.redraw) c.redraw();
    });
});


function mbpsToAmount(s) {
    return 1 - (1 / (Math.pow(1.3, Math.sqrt(s))));
}

function msToAmount(s) {
    return 1 - (1 / (Math.pow(1.08, Math.sqrt(s))));
}

function oscillate() {
    return 1 + 0.02 * Math.sin(Date.now() / 100);
}

function initUI() {
    drawMeter(I("dl_meter"), 0, meterBk, dlColor, 0);
    drawMeter(I("ul_meter"), 0, meterBk, ulColor, 0);
    drawMeter(I("ping_meter"), 0, meterBk, pingColor, 0);
    drawMeter(I("jitter_meter"), 0, meterBk, jitColor, 0);
    I("dl_text").textContent = "0.00";
    I("ul_text").textContent = "0.00";
    I("ping_text").textContent = "0.00";
    I("jitter_text").textContent = "0.00";


    var chart1ctx = document.getElementById('chart_du_area').getContext('2d');
    var chart2ctx = document.getElementById('chart_pj_area').getContext('2d');
    var dlDataset = {
        label: 'Download',
        fill: false,
        lineTension: 0.1,
        backgroundColor: alpha(dlColor, 0.5),
        borderColor: dlColor,
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: dlColor,
        pointBackgroundColor: surfaceColor,
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: dlColor,
        pointHoverBorderColor: 'rgba(220,220,220,1)',
        pointHoverBorderWidth: 2,
        pointRadius: 1,
        pointHitRadius: 10,
        data: [0],
        spanGaps: false
    }
    var ulDataset = {
        label: 'Upload',
        fill: false,
        lineTension: 0.1,
        backgroundColor: alpha(ulColor, 0.5),
        borderColor: ulColor,
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: ulColor,
        pointBackgroundColor: surfaceColor,
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: ulColor,
        pointHoverBorderColor: 'rgba(220,220,220,1)',
        pointHoverBorderWidth: 2,
        pointRadius: 1,
        pointHitRadius: 10,
        data: [0],
        spanGaps: false
    }
    var pingDataset = {
        label: 'Ping',
        fill: false,
        lineTension: 0.1,
        backgroundColor: alpha(pingColor, 0.5),
        borderColor: pingColor,
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: pingColor,
        pointBackgroundColor: surfaceColor,
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: pingColor,
        pointHoverBorderColor: 'rgba(220,220,220,1)',
        pointHoverBorderWidth: 2,
        pointRadius: 1,
        pointHitRadius: 10,
        data: [],
        spanGaps: false
    }
    var jitterDataset = {
        label: 'Jitter',
        fill: false,
        lineTension: 0.1,
        backgroundColor: alpha(jitColor, 0.5),
        borderColor: jitColor,
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: jitColor,
        pointBackgroundColor: surfaceColor,
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: jitColor,
        pointHoverBorderColor: 'rgba(220,220,220,1)',
        pointHoverBorderWidth: 2,
        pointRadius: 1,
        pointHitRadius: 10,
        data: [],
        spanGaps: false
    }

    var chart1Options = {
        type: 'line',
        data: {
            datasets: [dlDataset, ulDataset]
        },
        options: {
            responsive: true,
            tooltips: {
                enabled: false
            },
            legend: {
                position: 'top'
            },
            scales: {
                xAxes: [{
                    display: true,
                    scaleLabel: {
                        display: true,
                        labelString: tr('duration') + ' (s)'
                    },
                    ticks: {
                        beginAtZero: true
                    }
                }],
                yAxes: [{
                    display: true,
                    scaleLabel: {
                        display: true,
                        labelString: tr('speed') + ' (Mbps)'
                    },
                    ticks: {
                        beginAtZero: true
                    }
                }]
            }
        }
    }
    var chart2Options = {
        type: 'line',
        data: {
            datasets: [pingDataset, jitterDataset]
        },
        options: {
            responsive: true,
            tooltips: {
                enabled: false
            },
            legend: {
                position: 'top'
            },
            scales: {
                xAxes: [{
                    display: true,
                    scaleLabel: {
                        display: true,
                        labelString: tr('duration') + ' (ms)'
                    },
                    ticks: {
                        beginAtZero: true
                    }
                }],
                yAxes: [{
                    display: true,
                    scaleLabel: {
                        display: true,
                        labelString: tr('response') + ' (ms)'
                    },
                    ticks: {
                        beginAtZero: true
                    }
                }]
            }
        }
    }

    if (chart1 !== undefined) chart1.destroy();
    if (chart2 !== undefined) chart2.destroy();

    chart1 = new Chart(chart1ctx, chart1Options)
    chart2 = new Chart(chart2ctx, chart2Options)

    $('#results_table_download').html("<tr><th>" + tr("time") + " (s)</th><th>" + tr("speed") + " (Mbps)</th></tr>");
    $('#results_table_upload').html("<tr><th>" + tr("time") + " (s)</th><th>" + tr("speed") + " (Mbps)</th></tr>");
    max_download = 0;
    min_download = 0;
    max_upload = 0;
    min_upload = 0;
    total_download = 0;
    total_upload = 0;
    dl_samples = [];
    ul_samples = [];
    last_loaded_ping = null;
    last_loaded_jitter = null;
    unloaded_jitter = null;
    ping_sum = 0;
    ping_cnt = 0.001;
    $("#length").val(parameters.time_dl_max);
    // Show the full statistics table with placeholders, not just a message.
    updateStats();
}




function updateUI(forced) {
    if (!forced && (!data || !w)) return;
    var status = Number(data[0]);
    I("dl_text").textContent = (status == 1 && data[1] == 0) ? "..." : data[1];
    drawMeter(I("dl_meter"), mbpsToAmount(Number(data[1] * (status == 1 ? oscillate() : 1))), meterBk, dlColor, Number(data[6]), progColor);
    I("ul_text").textContent = (status == 3 && data[2] == 0) ? "..." : data[2];
    drawMeter(I("ul_meter"), mbpsToAmount(Number(data[2] * (status == 3 ? oscillate() : 1))), meterBk, ulColor, Number(data[7]), progColor);
    if (status === 2 && Number(data[3]) > 0) {
        ping_sum += Number(data[3]);
        ping_cnt++;
        unloaded_jitter = data[5];
    }
    // Once under-load samples exist the loaded loop owns the gauges;
    // otherwise the worker's 50ms updates and the 200ms loop visibly fight.
    if (!loadPing || !loadPing.samples.length) {
        I("ping_text").textContent = (ping_sum / ping_cnt).toFixed(2);
        drawMeter(I("ping_meter"), msToAmount(Number((ping_sum / ping_cnt) * (status == 2 ? oscillate() : 1))), meterBk, pingColor, Number(data[8]), progColor);
        I("jitter_text").textContent = data[5];
        drawMeter(I("jitter_meter"), msToAmount(Number(data[5] * (status == 2 ? oscillate() : 1))), meterBk, jitColor, Number(data[8]), progColor);
    }
    if (status === 1 && Number(data[1]) > 0) {
        // Chart update
        let chart_pos = ~~(parameters.time_dl_max * Number(data[6]));
        chart1.data.datasets[0].data[chart_pos] = (Number(data[1]));
        chart1.data.labels[chart1.data.datasets[0].data.length - 1] = chart_pos;
        chart1.update();
        // Table update
        if (last_chart_pos != chart_pos && chart_pos != 0) {
            $('#results_table_download').append("<tr><td>" + chart_pos + "</td><td>" + Number(data[1]) + "</td></tr>");
            dl_samples.push(Number(data[1]));
            if (Number(data[1]) > max_download || max_download <= 0) max_download = Number(data[1]);
            if (Number(data[1]) < min_download || min_download <= 0) min_download = Number(data[1]);
            total_download = data[9];
            updateStats();
            last_chart_pos = chart_pos;
        }

    }
    // Note: the final upload sample arrives tagged complete (status >= 4),
    // so the branch must accept it or the last second never records.
    if ((status === 3 || status >= 4) && Number(data[2]) > 0) {
        // Chart update
        let chart_pos = ~~(parameters.time_ul_max * Number(data[7]));
        chart1.data.datasets[1].data[chart_pos] = (Number(data[2]));
        chart1.data.labels[chart1.data.datasets[1].data.length - 1] = chart_pos;
        chart1.update();
        // Table update
        if (last_chart_pos != chart_pos && chart_pos != 0) {
            $('#results_table_upload').append("<tr><td>" + chart_pos + "</td><td>" + Number(data[2]) + "</td></tr>");
            ul_samples.push(Number(data[2]));
            last_chart_pos = chart_pos;
            if (Number(data[2]) > max_upload || max_upload <= 0) max_upload = Number(data[2]);
            if (Number(data[2]) < min_upload || min_upload <= 0) min_upload = Number(data[2]);
            total_upload = data[10];
            updateStats();
        }
        if (status >= 4) {
            // The worker only fills dlAmount/ulAmount at phase end, so
            // mid-run samples report 0 and a pre-completion second-15 row
            // freezes the totals at 0. Refresh them from the completion
            // sample unconditionally.
            total_download = data[9];
            total_upload = data[10];
            updateStats();
        }
    }
    if (status === 2 && Number(data[3]) > 0 && Number(data[8]) < 1) {
        chart2.data.datasets[0].data.push(Number(data[3]));
        chart2.data.datasets[1].data.push(Number(data[5]));
        chart2.data.labels[chart2.data.datasets[0].data.length - 1] = '';
        chart2.data.labels[chart2.data.datasets[1].data.length - 1] = Math.round(data[11] / 100) * 100;
        chart2.update();
    }
}

function avg(a) {
    return a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN;
}

function fmtStat(v, unit) {
    return isNaN(v) ? "n/a" : Number(v).toFixed(2) + " " + unit;
}

function stddev(a) {
    if (a.length < 2) return NaN;
    var m = avg(a);
    return Math.sqrt(a.reduce((x, y) => x + (y - m) * (y - m), 0) / (a.length - 1));
}

function updateStats() {
    var rows = [
        [tr("minimal_download"), min_download + " Mbps"],
        [tr("maximal_download"), max_download + " Mbps"],
        ["Average download:", fmtStat(avg(dl_samples), "Mbps")],
        [tr("minimal_upload"), min_upload + " Mbps"],
        [tr("maximal_upload"), max_upload + " Mbps"],
        ["Average upload:", fmtStat(avg(ul_samples), "Mbps")],
        [tr("total_download"), Math.round(total_download / 1024 / 1024) + " MB"],
        [tr("total_upload"), Math.round(total_upload / 1024 / 1024) + " MB"],
        ["Unloaded ping:", fmtStat(ping_sum / ping_cnt, "ms")],
        ["Unloaded jitter:", unloaded_jitter === null ? "n/a" : Number(unloaded_jitter).toFixed(2) + " ms"],
        ["Loaded ping:", last_loaded_ping === null ? "n/a" : fmtStat(last_loaded_ping, "ms")],
        ["Loaded jitter:", last_loaded_jitter === null ? "n/a" : fmtStat(last_loaded_jitter, "ms")]
    ];
    $('#stats_table').html(
        rows.map(function (r) { return "<tr><th>" + r[0] + "</th><td>" + r[1] + "</td></tr>"; }).join("")
    );
}


// Report the finished test to the WebUI, which stores it for the report page
// and the notifications tab. Same origin, so the session cookie authenticates
// it. Best-effort: never blocks or breaks the UI.
function reportResult() {
    var result = {
        download_mbps: avg(dl_samples),
        upload_mbps: avg(ul_samples),
        ping_ms: ping_cnt > 0 ? ping_sum / ping_cnt : null,
        jitter_ms: unloaded_jitter,
        loaded_ping_ms: last_loaded_ping,
        loaded_jitter_ms: last_loaded_jitter,
        download_min_mbps: min_download || null,
        download_max_mbps: max_download || null,
        upload_min_mbps: min_upload || null,
        upload_max_mbps: max_upload || null,
        download_mb: total_download ? total_download / 1024 / 1024 : null,
        upload_mb: total_upload ? total_upload / 1024 / 1024 : null,
        client_ip: data[4] || "",
        duration_s: (Number(parameters.time_dl_max) || 0) + (Number(parameters.time_ul_max) || 0)
    };
    fetch("/app/librespeed/results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(result)
    }).then(function (r) {
        return r.ok ? r.json() : null;
    }).then(function (saved) {
        if (saved && saved.url) showResultCard(result, saved.url);
    }).catch(function () { /* best-effort */ });
}

function showResultCard(result, url) {
    var el = I("result_card");
    if (!el) return;
    el.innerHTML =
        "<h2>Result</h2>" +
        '<p class="visually-hidden">' +
        fmtStat(result.download_mbps, "Mbps") + " down, " +
        fmtStat(result.upload_mbps, "Mbps") + " up, " +
        fmtStat(result.ping_ms, "ms") + " ping</p>" +
        '<p><a class="btn" href="' + url + '">View result</a> ' +
        '<a class="btn" href="/app/librespeed/results">All results</a></p>';
    el.style.display = "block";
}


function startStop() {
    if (w != null) {
        //speedtest is running, abort
        w.postMessage('abort');
        resetUI();
        initUI();
    } else {
        //update params
        let min = parseInt($("#length").attr('min'));
        let max = parseInt($("#length").attr('max'));
        let val = parseInt($("#length").val());
        if (val < min) val = min;
        if (val > max) val = max;
        parameters.time_dl_max = val;
        parameters.time_ul_max = val;
        initUI();
        //test is not running, begin
        w = new Worker("speedtest_worker.js?r=" + Math.random());
        w.postMessage('start ' + JSON.stringify(parameters)); //run the test with custom parameters
        loadPingStart();
        I("startStopBtn").className = "btn disabled";
        I("startStopBtn").disabled = true;
        I("startStopBtn").innerHTML = tr("abort");
        setTimeout(function() {
            I("startStopBtn").className = "btn running";
        }, 1500);
        w.onmessage = function(e) {
            var resData = JSON.parse(e.data);
            // testStatus, dlStatus, ulStatus, pingStatus, clientIp, jitterStatus, dlProgress, ulProgress, pingProgress, dlAmount, ulAmount;
            data[0] = resData.testState;
            data[1] = resData.dlStatus;
            data[2] = resData.ulStatus;
            data[3] = resData.pingStatus;
            data[4] = resData.clientIp;
            data[5] = resData.jitterStatus;
            data[6] = resData.dlProgress;
            data[7] = resData.ulProgress;
            data[8] = resData.pingProgress;
            data[9] = resData.dlAmount;
            data[10] = resData.ulAmount;
            var status = resData.testState;
            if (timers[1] == undefined && status == 1)
                timers[1] = performance.now();
            if (timers[2] == undefined && status == 2)
                timers[2] = performance.now();
            if (timers[3] == undefined && status == 3)
                timers[3] = performance.now();
            if (status >= 4) {
                //test completed: keep under-load samples, then restore UI
                if (loadPing && loadPing.samples.length) {
                    last_loaded_ping = avg(loadPing.samples);
                    last_loaded_jitter = loadPing.samples.length > 1 ? stddev(loadPing.samples) : 0;
                }
                resetUI();
                updateUI(true);
                reportResult();
            } else {
                data[11] = performance.now() - timers[status];
                updateUI();
            }
            setTimeout(function() {
                if (w != null) w.postMessage('status');
            }, 50);
        };
        w.postMessage('status');
    }
}

function resetUI() {
    I("startStopBtn").className = "btn";
    I("startStopBtn").disabled = false;
    I("startStopBtn").innerHTML = tr("start");
    w = null;
    sampling = false;
    loadPingStop();
    delete timers[1];
    delete timers[2];
    delete timers[3];
}

// Under-load ping: while the worker's own download/upload streams saturate
// the link (status 1/3), fire paced ping requests and show them live in the
// gauges. At completion the gauges revert to the unloaded finals and the
// loaded figures persist in the statistics table.
var loadPing = null;

function loadPingStart() {
    loadPingStop();
    loadPing = { samples: [], timer: setInterval(loadPingFire, 200) };
}

function loadPingStop() {
    if (!loadPing) return;
    clearInterval(loadPing.timer);
    loadPing = null;
}

function loadPingFire() {
    var st = data && Number(data[0]);
    if (st !== 1 && st !== 3) return;
    var xhr = new XMLHttpRequest();
    var t0 = performance.now();
    xhr.onload = function () {
        if (!loadPing) return;
        loadPing.samples.push(performance.now() - t0);
        // Paint only once the current phase is producing numbers itself,
        // so the loaded gauges never fill before download/upload do.
        var stNow = data && Number(data[0]);
        var phased = (stNow === 1 && Number(data[1]) > 0) || (stNow === 3 && Number(data[2]) > 0);
        if (!phased) return;
        var m = avg(loadPing.samples);
        I("ping_text").textContent = m.toFixed(2);
        drawMeter(I("ping_meter"), msToAmount(m), meterBk, pingColor, 1, progColor);
        if (loadPing.samples.length > 1) {
            var j = stddev(loadPing.samples);
            I("jitter_text").textContent = j.toFixed(2);
            drawMeter(I("jitter_meter"), msToAmount(j), meterBk, jitColor, 1, progColor);
        }
    };
    xhr.open("GET", parameters.url_ping + "?r=" + Math.random(), true);
    xhr.send();
}

window.addEventListener("storage", function (event) {
    if (event.key === "wlanpi-theme") applyLiveTheme(event.newValue);
});

window.addEventListener("focus", function(event) {
    try { applyLiveTheme(localStorage.getItem("wlanpi-theme")); } catch (e) {}
    if (!data) data = ["0", "", "", "", "", "", "0", "0", "0", 0];
    updateUI(true)
    chart1.update();
    chart2.update();
}, false);
