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
(trans.show_advanced = []),
(trans.show_advanced["en-US"] = "SHOW MORE DETAILS"),
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
(trans.ip_address = []),
(trans.ip_address["en-US"] = "Client IP Address:"),
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
(trans.show_detailed_a["en-US"] = "Click here"),
(trans.show_detailed_b = []),
(trans.show_detailed_b["en-US"] = "to toggle details about how <a href='https://github.com/librespeed/speedtest' target='_blank'>LibreSpeed</a> works and the algorithms involved."),
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
(trans.desc_questions["en-US"] = "For any questions regarding speedtest, please don't contact us.");
var chart1,
    chart2,
    last_chart_pos,
    meterBk = "#dadada",
    dlColor = "#6060aa",
    ulColor = "#309030",
    pingColor = "#ffcc00",
    jitColor = "#cc0000",
    progColor = "#EEEEEE",
    w = null,
    sampling = false,
    data = [],
    timers = [],
    parameters = {
        overheadCompensationFactor: 1.0, // 1 = raw performance
        mpot: false,
        forceIE11Workaround: false,
        test_order: 'IP_D_U',
        time_ul_max: 15,
        time_dl_max: 15,
        time_ulGraceTime: 3,
        time_dlGraceTime: 1.5,
        time_auto: false,
        count_ping: 100,
        enable_quirks: true,
        url_dl: "librespeed/garbage.dat",
        url_ul: "librespeed/empty.dat",
        url_ping: "librespeed/empty.dat",
        url_getIp: "librespeed/getip",
        getIp_ispInfo: false
    },
    max_upload = 0,
    min_upload = 0,
    max_download = 0,
    min_download = 0,
    total_upload = 0,
    total_download = 0,
    ping_sum = 0,
    ping_cnt = 0.001;


function drawMeter(c, amount, bk, fg, progress, prog) {
    var ctx = c.getContext("2d");
    var dp = window.devicePixelRatio || 1;
    var cw = c.clientWidth * dp,
        ch = c.clientHeight * dp;
    var sizScale = ch * 0.0055;
    if (c.width == cw && c.height == ch) {
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
    I("dl_text").textContent = "";
    I("ul_text").textContent = "";
    I("ping_text").textContent = "";
    I("jitter_text").textContent = "";
    I("ip").textContent = "?";


    var chart1ctx = document.getElementById('chart_du_area').getContext('2d');
    var chart2ctx = document.getElementById('chart_pj_area').getContext('2d');
    var dlDataset = {
        label: 'Download',
        fill: false,
        lineTension: 0.1,
        backgroundColor: 'rgba(96,96,170,0.5)',
        borderColor: 'rgba(96,96,170,1)',
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: 'rgba(96,96,170,1)',
        pointBackgroundColor: '#fff',
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: 'rgba(96,96,170,1)',
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
        backgroundColor: 'rgba(48,144,48,0.5)',
        borderColor: 'rgba(48,144,48,1)',
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: 'rgba(48,144,48,1)',
        pointBackgroundColor: '#fff',
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: 'rgba(48,144,48,1)',
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
        backgroundColor: 'rgba(255,204,0,0.5)',
        borderColor: 'rgba(255,204,0,1)',
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: 'rgba(255,204,0,1)',
        pointBackgroundColor: '#fff',
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: 'rgba(75,220,75,1)',
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
        backgroundColor: 'rgba(204,0,0,0.5)',
        borderColor: 'rgba(204,0,0,1)',
        borderCapStyle: 'butt',
        borderDash: [],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter',
        pointBorderColor: 'rgba(204,0,0,1)',
        pointBackgroundColor: '#fff',
        pointBorderWidth: 1,
        pointHoverRadius: 0,
        pointHoverBackgroundColor: 'rgba(220,75,75,1)',
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
    $('#stats_table').html("");
    max_download = 0;
    min_download = 0;
    max_upload = 0;
    min_upload = 0;
    total_download = 0;
    total_upload = 0;
    $("#length").val(parameters.time_dl_max);
}

$(document).ready(function() {
    $("#show_advanced").click(function() {
        $("#advanced").slideToggle(300);
    });
    $("#show_speedtest_info").click(function() {
        $("#speedtest_info").slideToggle(300);
    });
});



function updateUI(forced) {
    if (!forced && (!data || !w)) return;
    var status = Number(data[0]);
    I("ip").textContent = data[4];
    I("dl_text").textContent = (status == 1 && data[1] == 0) ? "..." : data[1];
    drawMeter(I("dl_meter"), mbpsToAmount(Number(data[1] * (status == 1 ? oscillate() : 1))), meterBk, dlColor, Number(data[6]), progColor);
    I("ul_text").textContent = (status == 3 && data[2] == 0) ? "..." : data[2];
    drawMeter(I("ul_meter"), mbpsToAmount(Number(data[2] * (status == 3 ? oscillate() : 1))), meterBk, ulColor, Number(data[7]), progColor);
    if (status === 2 && Number(data[3]) > 0) {
        ping_sum += Number(data[3]);
        ping_cnt++;
    }
    I("ping_text").textContent = (ping_sum / ping_cnt).toFixed(2);
    drawMeter(I("ping_meter"), msToAmount(Number((ping_sum / ping_cnt) * (status == 2 ? oscillate() : 1))), meterBk, pingColor, Number(data[8]), progColor);
    I("jitter_text").textContent = data[5];
    drawMeter(I("jitter_meter"), msToAmount(Number(data[5] * (status == 2 ? oscillate() : 1))), meterBk, jitColor, Number(data[8]), progColor);
    if (status === 1 && Number(data[1]) > 0) {
        // Chart update
        let chart_pos = ~~(parameters.time_dl_max * Number(data[6]));
        chart1.data.datasets[0].data[chart_pos] = (Number(data[1]));
        chart1.data.labels[chart1.data.datasets[0].data.length - 1] = chart_pos;
        chart1.update();
        // Table update
        if (last_chart_pos != chart_pos && chart_pos != 0) {
            $('#results_table_download').append("<tr><td>" + chart_pos + "</td><td>" + Number(data[1]) + "</td></tr>");
            if (Number(data[1]) > max_download || max_download <= 0) max_download = Number(data[1]);
            if (Number(data[1]) < min_download || min_download <= 0) min_download = Number(data[1]);
            total_download = data[9];
            updateStats();
            last_chart_pos = chart_pos;
        }

    }
    if (status === 3 && Number(data[2]) > 0) {
        // Chart update
        let chart_pos = ~~(parameters.time_ul_max * Number(data[7]));
        chart1.data.datasets[1].data[chart_pos] = (Number(data[2]));
        chart1.data.labels[chart1.data.datasets[1].data.length - 1] = chart_pos;
        chart1.update();
        // Table update
        if (last_chart_pos != chart_pos && chart_pos != 0) {
            $('#results_table_upload').append("<tr><td>" + chart_pos + "</td><td>" + Number(data[2]) + "</td></tr>");
            last_chart_pos = chart_pos;
            if (Number(data[2]) > max_upload || max_upload <= 0) max_upload = Number(data[2]);
            if (Number(data[2]) < min_upload || min_upload <= 0) min_upload = Number(data[2]);
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

function updateStats() {
    $('#stats_table').html("\
        <tr><th>" + tr("minimal_download") + "</th><td>" + min_download + " Mbps</td></tr>\
        <tr><th>" + tr("maximal_download") + "</th><td>" + max_download + " Mbps</td></tr>\
        <tr><th>" + tr("minimal_upload") + "</th><td>" + min_upload + " Mbps</td></tr>\
        <tr><th>" + tr("maximal_upload") + "</th><td>" + max_upload + " Mbps</td></tr>\
        <tr><th>" + tr("total_download") + "</th><td>" + Math.round(total_download / 1024 / 1024) + " MB</td></tr>\
        <tr><th>" + tr("total_upload") + "</th><td>" + Math.round(total_upload / 1024 / 1024) + " MB</td></tr>\
        ");
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
        I("startStopBtn").className = "btn disabled";
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
                //test completed
                resetUI();
                updateUI(true);
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
    I("startStopBtn").innerHTML = tr("start");
    w = null;
    sampling = false;
    delete timers[1];
    delete timers[2];
    delete timers[3];
}


window.addEventListener("focus", function(event) {
    if (!data) data = ["0", "", "", "", "", "", "0", "0", "0", 0];
    updateUI(true)
    chart1.update();
    chart2.update();
}, false);