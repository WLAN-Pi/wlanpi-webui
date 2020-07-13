var testStatus = -1,
    dlStatus = "",
    ulStatus = "",
    pingStatus = "",
    jitterStatus = "",
    clientIp = "",
    dlProgress = 0,
    ulProgress = 0,
    pingProgress = 0,
    testId = null,
    totDownload = 0,
    totUpload = 0,
    log = "";

function tlog(t) {
    settings.telemetry_level >= 2 && (log += Date.now() + ": " + t + "\n")
}

function tverb(t) {
    settings.telemetry_level >= 3 && (log += Date.now() + ": " + t + "\n")
}

function twarn(t) {
    settings.telemetry_level >= 2 && (log += Date.now() + " WARN: " + t + "\n"), console.warn(t)
}
var settings = {
        test_order: "IP_D_U",
        time_ul_max: 15,
        time_dl_max: 15,
        time_auto: !0,
        time_ulGraceTime: 3,
        time_dlGraceTime: 1.5,
        count_ping: 25,
        url_dl: "garbage.php",
        url_ul: "empty.php",
        url_ping: "empty.php",
        url_getIp: "getIP.php",
        getIp_ispInfo: !0,
        getIp_ispInfo_distance: "km",
        xhr_dlMultistream: 6,
        xhr_ulMultistream: 3,
        xhr_multistreamDelay: 300,
        xhr_ignoreErrors: 1,
        xhr_dlUseBlob: !1,
        xhr_ul_blob_megabytes: 20,
        garbagePhp_chunkSize: 10,
        enable_quirks: !0,
        ping_allowPerformanceApi: !0,
        overheadCompensationFactor: 1.06,
        useMebibits: !1,
        telemetry_level: 0,
        url_telemetry: "telemetry/telemetry.php",
        telemetry_extra: ""
    },
    xhr = null,
    interval = null,
    test_pointer = 0;

function url_sep(t) {
    return t.match(/\?/) ? "&" : "?"
}

function clearRequests() {
    if (tverb("stopping pending XHRs"), xhr) {
        for (var t = 0; t < xhr.length; t++) {
            try {
                xhr[t].onprogress = null, xhr[t].onload = null, xhr[t].onerror = null
            } catch (t) {}
            try {
                xhr[t].upload.onprogress = null, xhr[t].upload.onload = null, xhr[t].upload.onerror = null
            } catch (t) {}
            try {
                xhr[t].abort()
            } catch (t) {}
            try {
                delete xhr[t]
            } catch (t) {}
        }
        xhr = null
    }
}
this.addEventListener("message", function(t) {
    var e = t.data.split(" ");
    if ("status" === e[0] && postMessage(JSON.stringify({
            testState: testStatus,
            dlStatus: dlStatus,
            ulStatus: ulStatus,
            pingStatus: pingStatus,
            clientIp: clientIp,
            jitterStatus: jitterStatus,
            dlProgress: dlProgress,
            ulProgress: ulProgress,
            pingProgress: pingProgress,
            testId: testId,
            dlAmount: totDownload,
            ulAmount: totUpload
        })), "start" === e[0] && -1 === testStatus) {
        testStatus = 0;
        try {
            var r = {};
            try {
                var s = t.data.substring(5);
                s && (r = JSON.parse(s))
            } catch (t) {
                twarn("Error parsing custom settings JSON. Please check your syntax")
            }
            for (var n in r) void 0 !== settings[n] ? settings[n] = r[n] : twarn("Unknown setting ignored: " + n);
            if (settings.enable_quirks || void 0 !== r.enable_quirks && r.enable_quirks) {
                var i = navigator.userAgent;
                /Firefox.(\d+\.\d+)/i.test(i) && (void 0 === r.xhr_ulMultistream && (settings.xhr_ulMultistream = 1), void 0 === r.xhr_ulMultistream && (settings.ping_allowPerformanceApi = !1)), /Edge.(\d+\.\d+)/i.test(i) && void 0 === r.xhr_dlMultistream && (settings.xhr_dlMultistream = 3), /Chrome.(\d+)/i.test(i) && self.fetch && void 0 === r.xhr_dlMultistream && (settings.xhr_dlMultistream = 5)
            }
            /Edge.(\d+\.\d+)/i.test(i) && (settings.forceIE11Workaround = !0), /PlayStation 4.(\d+\.\d+)/i.test(i) && (settings.forceIE11Workaround = !0), /Chrome.(\d+)/i.test(i) && /Android|iPhone|iPad|iPod|Windows Phone/i.test(i) && (settings.xhr_ul_blob_megabytes = 4), void 0 !== r.telemetry_level && (settings.telemetry_level = "basic" === r.telemetry_level ? 1 : "full" === r.telemetry_level ? 2 : "debug" === r.telemetry_level ? 3 : 0), settings.test_order = settings.test_order.toUpperCase()
        } catch (t) {
            twarn("Possible error in custom test settings. Some settings may not be applied. Exception: " + t)
        }
        tverb(JSON.stringify(settings)), test_pointer = 0;
        var a = !1,
            o = !1,
            l = !1,
            u = !1,
            g = function() {
                if (5 != testStatus)
                    if (test_pointer >= settings.test_order.length) settings.telemetry_level > 0 ? sendTelemetry(function(t) {
                        testStatus = 4, null != t && (testId = t)
                    }) : testStatus = 4;
                    else switch (settings.test_order.charAt(test_pointer)) {
                        case "I":
                            if (test_pointer++, a) return void g();
                            a = !0, getIp(g);
                            break;
                        case "D":
                            if (test_pointer++, o) return void g();
                            o = !0, testStatus = 1, dlTest(g);
                            break;
                        case "U":
                            if (test_pointer++, l) return void g();
                            l = !0, testStatus = 3, ulTest(g);
                            break;
                        case "P":
                            if (test_pointer++, u) return void g();
                            u = !0, testStatus = 2, pingTest(g);
                            break;
                        case "_":
                            test_pointer++, setTimeout(g, 1e3);
                            break;
                        default:
                            test_pointer++
                    }
            };
        g()
    }
    "abort" === e[0] && (tlog("manually aborted"), clearRequests(), g = null, interval && clearInterval(interval), settings.telemetry_level > 1 && sendTelemetry(function() {}), testStatus = 5, dlStatus = "", ulStatus = "", pingStatus = "", jitterStatus = "")
});
var ipCalled = !1,
    ispInfo = "";

function getIp(t) {
    if (tverb("getIp"), !ipCalled) {
        ipCalled = !0;
        var e = (new Date).getTime();
        (xhr = new XMLHttpRequest).onload = function() {
            tlog("IP: " + xhr.responseText + ", took " + ((new Date).getTime() - e) + "ms");
            try {
                var r = JSON.parse(xhr.responseText);
                clientIp = r.processedString, ispInfo = r.rawIspInfo
            } catch (t) {
                clientIp = xhr.responseText, ispInfo = ""
            }
            t()
        }, xhr.onerror = function() {
            tlog("getIp failed, took " + ((new Date).getTime() - e) + "ms"), t()
        }, xhr.open("GET", settings.url_getIp + url_sep(settings.url_getIp) + (settings.getIp_ispInfo ? "isp=true" + (settings.getIp_ispInfo_distance ? "&distance=" + settings.getIp_ispInfo_distance + "&" : "&") : "&") + "r=" + Math.random(), !0), xhr.send()
    }
}
var dlCalled = !1;

function dlTest(t) {
    if (tverb("dlTest"), !dlCalled) {
        dlCalled = !0;
        var e = 0,
            r = (new Date).getTime(),
            s = 0,
            n = !1,
            i = !1;
        xhr = [];
        for (var a = function(t, r) {
                setTimeout(function() {
                    if (1 === testStatus) {
                        tverb("dl test stream started " + t + " " + r);
                        var s = 0,
                            n = new XMLHttpRequest;
                            xhr[t] = n, xhr[t].onprogress = function(r) {
                            if (tverb("dl stream progress event " + t + " " + r.loaded), 1 !== testStatus) try {
                                n.abort()
                            } catch (t) {}
                            var i = r.loaded <= 0 ? 0 : r.loaded - s;
                            isNaN(i) || !isFinite(i) || i < 0 || (totDownload = e += i, s = r.loaded)
                        }.bind(this), xhr[t].onload = function() {
                            tverb("dl stream finished " + t);
                            try {
                                xhr[t].abort()
                            } catch (t) {}
                            a(t, 0)
                        }.bind(this), xhr[t].onerror = function() {
                            tverb("dl stream failed " + t), 0 === settings.xhr_ignoreErrors && (i = !0);
                            try {
                                xhr[t].abort()
                            } catch (t) {}
                            delete xhr[t], 1 === settings.xhr_ignoreErrors && a(t, 0)
                        }.bind(this);
                        try {
                            settings.xhr_dlUseBlob ? xhr[t].responseType = "blob" : xhr[t].responseType = "arraybuffer"
                        } catch (t) {}
                        xhr[t].open("GET", settings.url_dl + url_sep(settings.url_dl) + "r=" + Math.random() + "&ckSize=" + settings.garbagePhp_chunkSize, !0), xhr[t].send()
                    }
                }.bind(this), 1 + r)
            }.bind(this), o = 0; o < settings.xhr_dlMultistream; o++) a(o, settings.xhr_multistreamDelay * o);
        interval = setInterval(function() {
            tverb("DL: " + dlStatus + (n ? "" : " (in grace time)"));
            var a = (new Date).getTime() - r;
            if (n && (dlProgress = (a + s) / (1e3 * settings.time_dl_max)), !(a < 200))
                if (n) {
                    var o = e / (a / 1e3);
                    if (settings.time_auto) {
                        var l = 6.4 * o / 1e5;
                        s += l > 800 ? 800 : l
                    }
                    dlStatus = (8 * o * settings.overheadCompensationFactor / (settings.useMebibits ? 1048576 : 1e6)).toFixed(2), ((a + s) / 1e3 > settings.time_dl_max || i) && ((i || isNaN(dlStatus)) && (dlStatus = "Fail"), clearRequests(), clearInterval(interval), dlProgress = 1, tlog("dlTest: " + dlStatus + ", took " + ((new Date).getTime() - r) + "ms"), t())
                } else a > 1e3 * settings.time_dlGraceTime && (e > 0 && (r = (new Date).getTime(), s = 0, e = 0), n = !0)
        }.bind(this), 200)
    }
}
var ulCalled = !1;

function ulTest(t) {
    if (tverb("ulTest"), !ulCalled) {
        ulCalled = !0;
        var e = new ArrayBuffer(1048576),
            r = Math.pow(2, 32) - 1;
        try {
            e = new Uint32Array(e);
            for (var s = 0; s < e.length; s++) e[s] = Math.random() * r
        } catch (t) {}
        var n = [],
            i = [];
        for (s = 0; s < settings.xhr_ul_blob_megabytes; s++) n.push(e);
        n = new Blob(n), e = new ArrayBuffer(262144);
        try {
            e = new Uint32Array(e);
            for (s = 0; s < e.length; s++) e[s] = Math.random() * r
        } catch (t) {}
        i.push(e), i = new Blob(i);
        var a = 0,
            o = (new Date).getTime(),
            l = 0,
            u = !1,
            g = !1;
        xhr = [];
        var d = function(t, e) {
            setTimeout(function() {
                if (3 === testStatus) {
                    tverb("ul test stream started " + t + " " + e);
                    var r, s = 0,
                        o = new XMLHttpRequest;
                    if (xhr[t] = o, settings.forceIE11Workaround) r = !0;
                    else try {
                        xhr[t].upload.onprogress, r = !1
                    } catch (t) {
                        r = !0
                    }
                    if (r) {
                        xhr[t].onload = xhr[t].onerror = function() {
                            tverb("ul stream progress event (ie11wa)"), a += i.size, totUpload = a, d(t, 0)
                        }, xhr[t].open("POST", settings.url_ul + url_sep(settings.url_ul) + "r=" + Math.random(), !0);
                        try {
                            xhr[t].setRequestHeader("Content-Encoding", "identity")
                        } catch (t) {}
                        try {
                            xhr[t].setRequestHeader("Content-Type", "application/octet-stream")
                        } catch (t) {}
                        xhr[t].send(i)
                    } else {
                        xhr[t].upload.onprogress = function(e) {
                            if (tverb("ul stream progress event " + t + " " + e.loaded), 3 !== testStatus) try {
                                o.abort()
                            } catch (t) {}
                            var r = e.loaded <= 0 ? 0 : e.loaded - s;
                            isNaN(r) || !isFinite(r) || r < 0 || (totUpload = a += r, s = e.loaded)
                        }.bind(this), xhr[t].upload.onload = function() {
                            tverb("ul stream finished " + t), d(t, 0)
                        }.bind(this), xhr[t].upload.onerror = function() {
                            tverb("ul stream failed " + t), 0 === settings.xhr_ignoreErrors && (g = !0);
                            try {
                                xhr[t].abort()
                            } catch (t) {}
                            delete xhr[t], 1 === settings.xhr_ignoreErrors && d(t, 0)
                        }.bind(this), xhr[t].open("POST", settings.url_ul + url_sep(settings.url_ul) + "r=" + Math.random(), !0);
                        try {
                            xhr[t].setRequestHeader("Content-Encoding", "identity")
                        } catch (t) {}
                        try {
                            xhr[t].setRequestHeader("Content-Type", "application/octet-stream")
                        } catch (t) {}
                        xhr[t].send(n)
                    }
                }
            }.bind(this), 1)
        }.bind(this);
        for (s = 0; s < settings.xhr_ulMultistream; s++) d(s, settings.xhr_multistreamDelay * s);
        interval = setInterval(function() {
            tverb("UL: " + ulStatus + (u ? "" : " (in grace time)"));
            var e = (new Date).getTime() - o;
            if (u && (ulProgress = (e + l) / (1e3 * settings.time_ul_max)), !(e < 200))
                if (u) {
                    var r = a / (e / 1e3);
                    if (settings.time_auto) {
                        var s = 6.4 * r / 1e5;
                        l += s > 800 ? 800 : s
                    }
                    ulStatus = (8 * r * settings.overheadCompensationFactor / (settings.useMebibits ? 1048576 : 1e6)).toFixed(2), ((e + l) / 1e3 > settings.time_ul_max || g) && ((g || isNaN(ulStatus)) && (ulStatus = "Fail"), clearRequests(), clearInterval(interval), ulProgress = 1, tlog("ulTest: " + ulStatus + ", took " + ((new Date).getTime() - o) + "ms"), t())
                } else e > 1e3 * settings.time_ulGraceTime && (a > 0 && (o = (new Date).getTime(), l = 0, a = 0), u = !0)
        }.bind(this), 200)
    }
}
var ptCalled = !1;

function pingTest(t) {
    if (tverb("pingTest"), !ptCalled) {
        ptCalled = !0;
        var e = (new Date).getTime(),
            r = null,
            s = 0,
            n = 0,
            i = 0,
            a = 0,
            o = 0;
        xhr = [];
        var l = function() {
            tverb("ping"), pingProgress = o / settings.count_ping, r = (new Date).getTime(), xhr[0] = new XMLHttpRequest, xhr[0].onload = function() {
                if (tverb("pong"), 0 === o) r = (new Date).getTime();
                else {
                    var u = (new Date).getTime() - r;
                    if (settings.ping_allowPerformanceApi) try {
                        var g = performance.getEntries(),
                            d = (g = g[g.length - 1]).responseStart - g.requestStart;
                        d <= 0 && (d = g.duration), d > 0 && d < u && (u = d)
                    } catch (t) {
                        tverb("Performance API not supported, using estimate")
                    }
                    u < .001 && (u = 0), u < .001 && (u = 1), i += u, a += u * u, s = u, n = Math.sqrt(a / o - Math.pow(i / o, 2))
                }
                pingStatus = s.toFixed(2), jitterStatus = n.toFixed(2), o++, tverb("ping: " + pingStatus + " jitter: " + jitterStatus), o < settings.count_ping ? setTimeout(l, 100) : (pingProgress = 1, tlog("ping: " + pingStatus + " jitter: " + jitterStatus + ", took " + ((new Date).getTime() - e) + "ms"), t())
            }.bind(this), xhr[0].onerror = function() {
                tverb("ping failed"), 0 === settings.xhr_ignoreErrors && (pingStatus = "Fail", jitterStatus = "Fail", clearRequests(), tlog("ping test failed, took " + ((new Date).getTime() - e) + "ms"), pingProgress = 1, t()), 1 === settings.xhr_ignoreErrors && l(), 2 === settings.xhr_ignoreErrors && (++o < settings.count_ping ? l() : (pingProgress = 1, tlog("ping: " + pingStatus + " jitter: " + jitterStatus + ", took " + ((new Date).getTime() - e) + "ms"), t()))
            }.bind(this), xhr[0].open("GET", settings.url_ping + url_sep(settings.url_ping) + "r=" + Math.random(), !0), xhr[0].send()
        }.bind(this);
        l()
    }
}

function sendTelemetry(t) {
    if (!(settings.telemetry_level < 1)) {
        (xhr = new XMLHttpRequest).onload = function() {
            try {
                var e = xhr.responseText.split(" ");
                if ("id" == e[0]) try {
                    var r = e[1];
                    t(r)
                } catch (e) {
                    t(null)
                } else t(null)
            } catch (e) {
                t(null)
            }
        }, xhr.onerror = function() {
            console.log("TELEMETRY ERROR " + xhr.status), t(null)
        }, xhr.open("POST", settings.url_telemetry + url_sep(settings.url_telemetry) + "r=" + Math.random(), !0);
        var e = {
            processedString: clientIp,
            rawIspInfo: "object" == typeof ispInfo ? ispInfo : ""
        };
        try {
            var r = new FormData;
            r.append("ispinfo", JSON.stringify(e)), r.append("dl", dlStatus), r.append("ul", ulStatus), r.append("ping", pingStatus), r.append("jitter", jitterStatus), r.append("log", settings.telemetry_level > 1 ? log : ""), r.append("extra", settings.telemetry_extra), xhr.send(r)
        } catch (t) {
            var s = "extra=" + encodeURIComponent(settings.telemetry_extra) + "&ispinfo=" + encodeURIComponent(JSON.stringify(e)) + "&dl=" + encodeURIComponent(dlStatus) + "&ul=" + encodeURIComponent(ulStatus) + "&ping=" + encodeURIComponent(pingStatus) + "&jitter=" + encodeURIComponent(jitterStatus) + "&log=" + encodeURIComponent(settings.telemetry_level > 1 ? log : "");
            xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded"), xhr.send(s)
        }
    }
}
