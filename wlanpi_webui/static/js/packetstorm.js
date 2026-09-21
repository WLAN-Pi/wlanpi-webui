/* Packet Storm: a hidden Wi-Fi themed Asteroids clone for the WLAN Pi WebUI.
 *
 * Loaded only on /packetstorm. Re-executing this file tears down any previous
 * instance first, so htmx swaps never stack loops or listeners.
 */
(function () {
  "use strict";

  if (window.__packetstorm) {
    try {
      window.__packetstorm();
    } catch (e) {
      /* ignore */
    }
    window.__packetstorm = null;
  }

  var stage = document.getElementById("packetstorm-stage");
  var canvas = document.getElementById("packetstorm-canvas");
  var hud = document.getElementById("packetstorm-hud");
  var touch = document.getElementById("packetstorm-touch");
  if (!stage || !canvas) {
    return;
  }
  var ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  var TAU = Math.PI * 2;
  var STEP = 1 / 60;
  var DFS_DUR = 1.8;
  var CLEAR_DUR = 2.5;
  var PMF_R = 70;
  var REDUCED = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // ---- Persistence ------------------------------------------------------
  var LS_KEY = "wlanpi:packetstorm:v1";
  var store = { high: 0, mute: true, difficulty: "normal" };
  try {
    var rawStore = window.localStorage.getItem(LS_KEY);
    if (rawStore) {
      var parsed = JSON.parse(rawStore);
      if (parsed) {
        store = {
          high: +parsed.high || 0,
          mute: parsed.mute !== false,
          difficulty: parsed.difficulty === "easy" ? "easy" : "normal"
        };
      }
    }
  } catch (e) {
    /* storage unavailable, in-memory state only */
  }
  function saveStore() {
    try {
      window.localStorage.setItem(LS_KEY, JSON.stringify(store));
    } catch (e) {
      /* ignore */
    }
  }

  // Hidden page arming: fired once when the player reaches the first 6 GHz
  // level. No anti-cheat by design; the endpoint is idempotent and guarded by
  // the session CSRF token only.
  var CSRF = stage.getAttribute("data-csrf") || "";
  var DEBUG = stage.getAttribute("data-debug") === "1";
  var armed = false;
  function armBeacon() {
    if (armed) {
      return;
    }
    armed = true;
    try {
      fetch("/beacon/arm", {
        method: "POST",
        credentials: "same-origin",
        headers: CSRF ? { "X-CSRF-Token": CSRF } : {}
      })
        .then(function (resp) {
          if (!resp.ok) {
            return;
          }
          // The only signal: one muted HUD line, gone with the transition.
          S = Object.assign({}, S);
          S.hint = { text: "unlicensed band available", ttl: 2.4 };
        })
        .catch(function () {
          /* a failure notice is louder than the success: stay silent */
        });
    } catch (e) {
      /* ignore */
    }
  }

  // ---- Audio (off by default, WebAudio oscillators only) ----------------
  var actx = null;
  function beep(freq, dur, type) {
    if (store.mute) {
      return;
    }
    try {
      if (!actx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) {
          return;
        }
        actx = new AC();
      }
      if (actx.state === "suspended") {
        actx.resume();
      }
      var o = actx.createOscillator();
      var g = actx.createGain();
      o.type = type || "square";
      o.frequency.value = freq;
      g.gain.value = 0.04;
      o.connect(g);
      g.connect(actx.destination);
      o.start();
      o.stop(actx.currentTime + dur);
    } catch (e) {
      /* ignore */
    }
  }

  // ---- Theme ------------------------------------------------------------
  function readTheme() {
    var out = {
      brand: "#f45625", page: "#101417", surface: "#1a2026", text: "#e6eaee",
      muted: "#9aa5b1", border: "#2a343d",
      danger: "#d32f2f", ok: "#2e7d32", info: "#0277bd",
      mono: "ui-monospace, Menlo, Consolas, monospace"
    };
    try {
      var cs = getComputedStyle(document.documentElement);
      var get = function (n) {
        var v = cs.getPropertyValue(n);
        return v ? v.trim() : "";
      };
      out.brand = get("--brand") || out.brand;
      out.page = get("--bg-page") || out.page;
      out.surface = get("--bg-surface") || out.surface;
      out.text = get("--text") || out.text;
      out.muted = get("--text-muted") || out.muted;
      out.border = get("--border") || out.border;
      out.danger = get("--danger") || out.danger;
      out.ok = get("--success") || out.ok;
      out.info = get("--info") || out.info;
      out.mono = get("--font-mono") || out.mono;
    } catch (e) {
      /* fall back to defaults */
    }
    return out;
  }
  var THEME = readTheme();

  // ---- Helpers ----------------------------------------------------------
  function rand(a, b) {
    return a + Math.random() * (b - a);
  }
  function pick(arr) {
    return arr[(Math.random() * arr.length) | 0];
  }
  function wrap(v, max) {
    if (v < 0) {
      return v + max;
    }
    if (v >= max) {
      return v - max;
    }
    return v;
  }
  function dist2(ax, ay, bx, by) {
    var dx = ax - bx;
    var dy = ay - by;
    return dx * dx + dy * dy;
  }
  function fmtAirtime(ms) {
    return (ms / 1000).toFixed(1) + "s";
  }

  // ---- Level spec: band and channel progression -------------------------
  var SOURCES = ["MICROWAVE", "BABY MONITOR", "CORDLESS PHONE", "BT CLUSTER", "FPV DRONE", "RF JAMMER", "VIDEO CAMERA"];
  var ROGUE_SSIDS = ["Free_WiFi", "xfinitywifi", "Hotel_WiFi", "Printer_Setup", "Guest_Net"];
  // Channel-width boosters: beam count and angular step per width. 160 MHz
  // needs 5 GHz, 320 MHz needs 6 GHz.
  var SPREAD = {
    "40": { beams: 3, step: 0.12 },
    "80": { beams: 5, step: 0.12 },
    "160": { beams: 7, step: 0.11 },
    "320": { beams: 9, step: 0.10 }
  };
  function dropTable(band) {
    var t = ["40", "MU", "BF", "W3", "CSA", "PMF", "W2"];
    if (band === "5 GHz" || band === "6 GHz") {
      t.push("80", "160");
    }
    if (band === "6 GHz") {
      t.push("320");
    }
    return t;
  }
  function beamAngles(count, step) {
    var out = [];
    var mid = (count - 1) / 2;
    var i;
    for (i = 0; i < count; i++) {
      out.push((i - mid) * step);
    }
    return out;
  }
  function pickMimoAngle() {
    var r = Math.random();
    var deg;
    if (r < 0.25) {
      deg = rand(30, 60);
    } else if (r < 0.65) {
      deg = rand(60, 90);
    } else {
      deg = rand(120, 180);
    }
    return (deg * Math.PI) / 180;
  }
  // 5 GHz progression: first non-DFS, then a DFS channel, then non-DFS, and
  // finally channel 165 with VTX bursts. 6 GHz adds AFC, puncturing, wide
  // 320 MHz congestion, and VTX from level 9.
  var FIVE_GHZ = [
    { ch: 36, dfs: false, vtx: false },
    { ch: 100, dfs: true, vtx: false },
    { ch: 149, dfs: false, vtx: false },
    { ch: 165, dfs: false, vtx: true }
  ];
  function levelSpec(n) {
    if (n <= 3) {
      return {
        band: "2.4 GHz", ch: [1, 6, 11][(n - 1) % 3],
        rocks: 3 + n, speed: 22 + 7 * n, zones: 3, noise: 0.15 + 0.05 * n,
        rogues: 0, dfs: false, afc: false, vtx: false, punct: false,
        zoneW: [56, 110], zoneSlow: 0.55
      };
    }
    if (n <= 7) {
      var f = FIVE_GHZ[(n - 4) % 4];
      return {
        band: "5 GHz", ch: f.ch,
        rocks: 4 + n, speed: 45 + 9 * n, zones: 2, noise: 0.3 + 0.05 * n,
        rogues: 1, dfs: f.dfs, afc: false, vtx: f.vtx, punct: false,
        zoneW: [56, 110], zoneSlow: 0.55
      };
    }
    return {
      band: "6 GHz", ch: [5, 21, 37, 53, 69, 85][(n - 8) % 6],
      rocks: 6 + n, speed: 70 + 8 * n, zones: 1, noise: 0.45 + 0.03 * n,
      rogues: 2, dfs: false, afc: true, vtx: n >= 9, punct: true,
      zoneW: [120, 200], zoneSlow: 0.4
    };
  }
  var TIER_R = [11, 20, 34];
  var TIER_SCORE = [60, 25, 10];
  var LINK_RATES = [54, 150, 300, 433, 866, 1200, 2400];

  // Easy mode slows the field down and lengthens the telegraphs.
  var DIFFICULTIES = {
    normal: { rockSpeed: 1, rogueCool: 1, shipCool: 1, rssiDecay: 1, warn: 1, retries: 0 },
    easy: { rockSpeed: 0.85, rogueCool: 1.25, shipCool: 0.85, rssiDecay: 0.75, warn: 1.3, retries: 1 }
  };
  function diff() {
    return DIFFICULTIES[store.difficulty] || DIFFICULTIES.normal;
  }

  function edgeSpawn(w, h, margin) {
    var side = (Math.random() * 4) | 0;
    if (side === 0) {
      return { x: rand(0, w), y: margin };
    }
    if (side === 1) {
      return { x: rand(0, w), y: h - margin };
    }
    if (side === 2) {
      return { x: margin, y: rand(0, h) };
    }
    return { x: w - margin, y: rand(0, h) };
  }

  function spawnRocks(w, h, level, spec) {
    var rocks = [];
    var i, p, guard;
    for (i = 0; i < spec.rocks; i++) {
      guard = 0;
      do {
        p = edgeSpawn(w, h, 60);
        guard++;
      } while (guard < 12 && dist2(p.x, p.y, w / 2, h / 2) < 170 * 170);
      var a = rand(0, TAU);
      var sp = rand(spec.speed * 0.6, spec.speed) * diff().rockSpeed;
      rocks.push({
        x: p.x, y: p.y,
        vx: Math.cos(a) * sp, vy: Math.sin(a) * sp,
        tier: 2, seed: Math.random() * 1000,
        name: SOURCES[i % SOURCES.length]
      });
    }
    return rocks;
  }

  function makeZones(w, spec) {
    var zones = [];
    var i;
    var range = spec.zoneW || [56, 110];
    for (i = 0; i < spec.zones; i++) {
      zones.push({ x: rand(0, w), w: rand(range[0], range[1]), dir: Math.random() < 0.5 ? -1 : 1 });
    }
    return zones;
  }

  function initialState(w, h) {
    var spec = levelSpec(1);
    return {
      w: w, h: h, t: 0, uptime: 0, phase: "play",
      ship: {
        x: w / 2, y: h / 2, vx: 0, vy: 0, a: -Math.PI / 2,
        rssi: -30, retries: 3 + diff().retries, invuln: 0, cool: 0, thrusting: false,
        respawnWait: 0
      },
      packets: [], rocks: spawnRocks(w, h, 1, spec),
      rogues: [], deauths: [],
      zones: makeZones(w, spec),
      powers: [], parts: [],
      fx: { spread: 0, spreadKind: "40", mimo: 0, mimoAngle: 1.2, beam: 0, wpa3: 0, pmf: 0, wpa2: 0 },
      combo: 0, score: 0, kills: 0, sent: 0, hits: 0, gains: [],
      dfs: { active: 0, y: 0, cool: 7, hitDone: false, dir: 1 },
      afc: { phase: "idle", timer: 0, y: 0, cool: 8, hitDone: false },
      vtx: { phase: "idle", timer: 0, x: 0, cool: 6, hitDone: false },
      punctures: [], punctCool: 5,
      banner: { text: "LEVEL 1  " + spec.band + " / ch " + spec.ch, ttl: 2.4 },
      shieldDropT: 0, intro: true, diff: store.difficulty || "normal",
      shake: 0, noise: spec.noise, spec: spec,
      level: 1, band: spec.band, ch: spec.ch,
      paused: false, autoPaused: false, clearTimer: 0,
      over: null
    };
  }

  function gotoLevel(S, level) {
    var n = Object.assign({}, S);
    n.level = level;
    n.spec = levelSpec(n.level);
    n.band = n.spec.band;
    n.ch = n.spec.ch;
    n.noise = n.spec.noise;
    n.rocks = spawnRocks(n.w, n.h, n.level, n.spec);
    n.zones = makeZones(n.w, n.spec);
    n.rogues = [];
    var i;
    for (i = 0; i < n.spec.rogues; i++) {
      var p = edgeSpawn(n.w, n.h, 60);
      n.rogues.push({ x: p.x, y: p.y, vx: 0, vy: 0, cool: rand(1, 3), ssid: pick(ROGUE_SSIDS), mlo: n.spec.band === "6 GHz" });
    }
    n.deauths = [];
    n.dfs = { active: 0, y: 0, cool: 6, hitDone: false, dir: 1 };
    n.afc = { phase: "idle", timer: 0, y: 0, cool: 8, hitDone: false };
    n.vtx = { phase: "idle", timer: 0, x: 0, cool: 6, hitDone: false };
    n.punctures = [];
    n.punctCool = 5;
    n.diff = store.difficulty || "normal";
    n.banner = { text: "LEVEL " + n.level + "  " + n.band + " / ch " + n.ch, ttl: 2.4 };
    n.shieldDropT = 0;
    n.phase = "play";
    n.clearTimer = 0;
    if (n.level === 8) {
      armBeacon();
    }
    return n;
  }

  function nextLevel(S) {
    return gotoLevel(S, S.level + 1);
  }

  // Debug-only level jump. Inert unless the server rendered data-debug.
  function jumpLevel(delta) {
    if (S.phase === "over") {
      return;
    }
    S = gotoLevel(S, Math.max(1, S.level + delta));
    hudTimer = -1;
  }

  // ---- Input ------------------------------------------------------------
  var held = { left: false, right: false, thrust: false, fire: false };

  // ---- update: pure, returns a new state --------------------------------
  function update(S, dt, input) {
    if (S.phase === "over" || S.paused || S.intro) {
      return S;
    }
    var n = Object.assign({}, S);
    n.t = S.t + dt;
    n.uptime = S.uptime + dt;
    n.gains = S.gains.filter(function (g) {
      return n.t - g.t < 3;
    });

    var ship = Object.assign({}, S.ship);
    n.ship = ship;

    if (S.phase === "clear") {
      n.clearTimer = S.clearTimer - dt;
      n.banner = { text: "", ttl: 0 };
      if (n.clearTimer <= 0) {
        return nextLevel(n);
      }
      return n;
    }

    // Ship rotation, thrust, drag.
    if (input.left) {
      ship.a -= 4.4 * dt;
    }
    if (input.right) {
      ship.a += 4.4 * dt;
    }
    ship.thrusting = !!input.thrust;
    if (input.thrust) {
      ship.vx += Math.cos(ship.a) * 320 * dt;
      ship.vy += Math.sin(ship.a) * 320 * dt;
    }
    var drag = 1 - Math.min(0.9, 0.55 * dt);
    ship.vx *= drag;
    ship.vy *= drag;
    ship.x = wrap(ship.x + ship.vx * dt, n.w);
    ship.y = wrap(ship.y + ship.vy * dt, n.h);
    if (ship.invuln > 0) {
      ship.invuln -= dt;
    }
    if (ship.cool > 0) {
      ship.cool -= dt;
    }
    if (ship.respawnWait > 0) {
      ship.respawnWait -= dt;
      var blocked = S.rocks.some(function (r) {
        return dist2(r.x, r.y, n.w / 2, n.h / 2) < 95 * 95;
      });
      // Refuse to respawn while the center is occupied.
      if (ship.respawnWait <= 0 && !blocked && ship.retries >= 0) {
        ship.x = n.w / 2;
        ship.y = n.h / 2;
        ship.vx = 0;
        ship.vy = 0;
        ship.invuln = 3;
      } else if (ship.respawnWait <= 0 && blocked) {
        ship.respawnWait = 0.5;
      }
    }

    var fx = {
      spread: Math.max(0, S.fx.spread - dt),
      spreadKind: S.fx.spreadKind || "40",
      mimo: Math.max(0, S.fx.mimo - dt),
      mimoAngle: S.fx.mimoAngle || 1.2,
      beam: Math.max(0, S.fx.beam - dt),
      wpa3: Math.max(0, S.fx.wpa3 - dt),
      pmf: Math.max(0, S.fx.pmf - dt),
      wpa2: Math.max(0, S.fx.wpa2 - dt)
    };
    n.fx = fx;

    var inZone = function (x) {
      return S.zones.some(function (z) {
        return Math.abs(x - z.x) < z.w / 2;
      });
    };

    // Firing: rate limited, capped live packets.
    var packets = S.packets.map(function (p) {
      return Object.assign({}, p);
    });
    var fired = 0;
    if (input.fire && ship.cool <= 0 && ship.respawnWait <= 0 && packets.length < 16) {
      ship.cool = 0.22 * diff().shipCool;
      var spreadCfg = SPREAD[fx.spreadKind] || SPREAD["40"];
      var angles = fx.spread > 0 ? beamAngles(spreadCfg.beams, spreadCfg.step) : [0];
      // MU-MIMO: two spatial streams, offset to the sides and angled apart by
      // the separation picked when the booster was collected.
      var sep = fx.mimoAngle || 1.2;
      var half = sep / 2;
      var sideOff = 12 + sep * 6;
      var emitters = fx.mimo > 0
        ? [{ off: -sideOff, da: -half }, { off: sideOff, da: half }]
        : [{ off: 0, da: 0 }];
      var px = Math.cos(ship.a);
      var py = Math.sin(ship.a);
      emitters.forEach(function (em) {
        var ox = ship.x + -py * em.off;
        var oy = ship.y + px * em.off;
        var base = ship.a + em.da;
        angles.forEach(function (da) {
          var sp = 460 * (inZone(ox) ? (S.spec.zoneSlow || 0.55) : 1);
          packets.push({
            x: ox, y: oy,
            vx: Math.cos(base + da) * sp + ship.vx * 0.4,
            vy: Math.sin(base + da) * sp + ship.vy * 0.4,
            life: 1.6, ghost: false
          });
          fired++;
        });
      });
      beep(880, 0.05, "square");
    }
    n.sent = S.sent + fired;

    // Packets: move, beamforming homing, expire, retransmit ghosts.
    var kept = [];
    packets.forEach(function (p) {
      p.life -= dt;
      if (fx.beam > 0 && S.rocks.length) {
        var best = null;
        var bd = Infinity;
        S.rocks.forEach(function (r) {
          var d = dist2(p.x, p.y, r.x, r.y);
          if (d < bd) {
            bd = d;
            best = r;
          }
        });
        if (best) {
          var want = Math.atan2(best.y - p.y, best.x - p.x);
          var cur = Math.atan2(p.vy, p.vx);
          var diff = want - cur;
          while (diff > Math.PI) {
            diff -= TAU;
          }
          while (diff < -Math.PI) {
            diff += TAU;
          }
          var turn = Math.max(-3 * dt, Math.min(3 * dt, diff));
          var sp = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
          var na = cur + turn;
          p.vx = Math.cos(na) * sp;
          p.vy = Math.sin(na) * sp;
        }
      }
      p.x = wrap(p.x + p.vx * dt, n.w);
      p.y = wrap(p.y + p.vy * dt, n.h);
      if (p.life > 0) {
        kept.push(p);
      } else if (!p.ghost && Math.random() < 0.12) {
        // Retransmit: ghost back toward the ship for a second pass.
        var ga = Math.atan2(ship.y - p.y, ship.x - p.x);
        kept.push({ x: p.x, y: p.y, vx: Math.cos(ga) * 380, vy: Math.sin(ga) * 380, life: 1.2, ghost: true });
      }
    });
    n.packets = kept;

    // Rocks drift.
    n.rocks = S.rocks.map(function (r) {
      return { x: wrap(r.x + r.vx * dt, n.w), y: wrap(r.y + r.vy * dt, n.h), vx: r.vx, vy: r.vy, tier: r.tier, seed: r.seed, name: r.name };
    });

    // Congestion zones drift.
    n.zones = S.zones.map(function (z) {
      var nx = z.x + z.dir * 14 * dt;
      if (nx < -z.w / 2) {
        nx += n.w + z.w;
      }
      if (nx > n.w + z.w / 2) {
        nx -= n.w + z.w;
      }
      return { x: nx, w: z.w, dir: z.dir };
    });

    // Power-ups drift and expire.
    n.powers = [];
    S.powers.forEach(function (pu) {
      var ttl = pu.ttl - dt;
      if (ttl <= 0) {
        return;
      }
      var np = { x: wrap(pu.x + pu.vx * dt, n.w), y: wrap(pu.y + pu.vy * dt, n.h), vx: pu.vx, vy: pu.vy, kind: pu.kind, ttl: ttl };
      if (ship.respawnWait <= 0 && dist2(np.x, np.y, ship.x, ship.y) < 26 * 26) {
        applyPowerup(n, np.kind);
        beep(1320, 0.08, "sine");
      } else {
        n.powers.push(np);
      }
    });

    // Rogue APs home slowly and fire deauth frames.
    var deauths = S.deauths.map(function (d) {
      return Object.assign({}, d);
    });
    n.rogues = S.rogues.map(function (g) {
      var ng = Object.assign({}, g);
      var ga = Math.atan2(ship.y - g.y, ship.x - g.x);
      ng.vx += Math.cos(ga) * 26 * dt;
      ng.vy += Math.sin(ga) * 26 * dt;
      var gs = Math.sqrt(ng.vx * ng.vx + ng.vy * ng.vy);
      if (gs > 46) {
        ng.vx = (ng.vx / gs) * 46;
        ng.vy = (ng.vy / gs) * 46;
      }
      ng.x = wrap(ng.x + ng.vx * dt, n.w);
      ng.y = wrap(ng.y + ng.vy * dt, n.h);
      ng.cool -= dt;
      if (ng.cool <= 0 && ship.respawnWait <= 0) {
        ng.cool = Math.max(1.2, 2.8 - S.level * 0.12) * diff().rogueCool;
        var da = Math.atan2(ship.y - ng.y, ship.x - ng.x);
        if (ng.mlo) {
          // MLO: two bonded links fire two deauth frames.
          [-0.18, 0.18].forEach(function (off) {
            deauths.push({ x: ng.x, y: ng.y, vx: Math.cos(da + off) * 230, vy: Math.sin(da + off) * 230, life: 4 });
          });
        } else {
          deauths.push({ x: ng.x, y: ng.y, vx: Math.cos(da) * 230, vy: Math.sin(da) * 230, life: 4 });
        }
        beep(220, 0.12, "sawtooth");
      }
      return ng;
    });
    var keptDeauth = [];
    deauths.forEach(function (d) {
      d.life -= dt;
      if (fx.wpa2 > 0 && ship.respawnWait <= 0) {
        // WPA2 downgrade: rogues beamform their deauth frames at the client.
        var want = Math.atan2(ship.y - d.y, ship.x - d.x);
        var cur = Math.atan2(d.vy, d.vx);
        var diff = want - cur;
        while (diff > Math.PI) {
          diff -= TAU;
        }
        while (diff < -Math.PI) {
          diff += TAU;
        }
        var turn = Math.max(-4.5 * dt, Math.min(4.5 * dt, diff));
        var spd = Math.sqrt(d.vx * d.vx + d.vy * d.vy);
        var na = cur + turn;
        d.vx = Math.cos(na) * spd;
        d.vy = Math.sin(na) * spd;
      }
      d.x = wrap(d.x + d.vx * dt, n.w);
      d.y = wrap(d.y + d.vy * dt, n.h);
      if (d.life > 0) {
        keptDeauth.push(d);
      }
    });
    n.deauths = keptDeauth;

    // Packet vs rock collisions.
    var livePackets = [];
    var rocks = n.rocks;
    var kills = S.kills;
    var hits = S.hits || 0;
    var score = S.score;
    var combo = S.combo;
    var gains = n.gains;
    var parts = S.parts.map(function (p) {
      return Object.assign({}, p);
    });

    // DFS radar sweep on 5 GHz levels. The band is dangerous only once the
    // sweep front has passed the ship, so the player can still fly clear.
    var dfs = Object.assign({}, S.dfs);
    if (S.spec.dfs && S.phase === "play") {
      dfs.cool -= dt;
      if (dfs.cool <= 0 && dfs.active <= 0) {
        dfs.active = DFS_DUR;
        dfs.y = rand(n.h * 0.2, n.h * 0.8);
        dfs.hitDone = false;
        // Sweep in from the side the player is not on, so they can clear it.
        dfs.dir = ship.x < n.w / 2 ? -1 : 1;
        n.banner = { text: "DFS RADAR", ttl: 1.6 };
        beep(440, 0.2, "sawtooth");
      }
      if (dfs.active > 0) {
        dfs.active -= dt;
        var dfsProg = 1 - Math.max(0, dfs.active) / DFS_DUR;
        var front = dfs.dir > 0 ? dfsProg * n.w : (1 - dfsProg) * n.w;
        var inBand = Math.abs(ship.y - dfs.y) < 34;
        var reached = dfs.dir > 0 ? ship.x <= front : ship.x >= front;
        if (inBand && reached && ship.respawnWait <= 0) {
          if (!dfs.hitDone) {
            dfs.hitDone = true;
            n.banner = { text: "RADAR HIT, CLEAR THE BAND", ttl: 1.4 };
          }
          var dfsApplied = damageRssi(n, ship, 26 * dt);
          if (dfsApplied) {
            burst(parts, ship.x, ship.y, REDUCED ? 1 : 3);
            n.shake = Math.max(n.shake || 0, 4);
          }
        }
      }
    }
    n.dfs = dfs;

    // AFC: 6 GHz coordination. A stationary band is announced, then locked;
    // staying inside the locked band drains the link.
    var afc = Object.assign({}, S.afc);
    if (S.spec.afc && S.phase === "play") {
      if (afc.phase === "idle") {
        afc.cool -= dt;
        if (afc.cool <= 0) {
          afc.phase = "warn";
          afc.timer = 1.5 * diff().warn;
          afc.y = rand(n.h * 0.2, n.h * 0.8);
          afc.hitDone = false;
          n.banner = { text: "AFC CHECK", ttl: 1.4 };
          beep(520, 0.15, "triangle");
        }
      } else if (afc.phase === "warn") {
        afc.timer -= dt;
        if (afc.timer <= 0) {
          afc.phase = "live";
          afc.timer = 3;
          beep(300, 0.2, "sawtooth");
        }
      } else if (afc.phase === "live") {
        afc.timer -= dt;
        if (Math.abs(ship.y - afc.y) < 30 && ship.respawnWait <= 0) {
          if (!afc.hitDone) {
            afc.hitDone = true;
            n.banner = { text: "AFC LOCKED", ttl: 1.2 };
          }
          if (damageRssi(n, ship, 22 * dt)) {
            burst(parts, ship.x, ship.y, REDUCED ? 1 : 3);
            n.shake = Math.max(n.shake || 0, 4);
          }
        }
        if (afc.timer <= 0) {
          afc.phase = "idle";
          afc.cool = 8;
        }
      }
    }
    n.afc = afc;

    // VTX: a video transmitter seen as a carrier spike on a spectrum analyzer.
    // It is announced, then fires a full-height spike with noise shoulders.
    var vtx = Object.assign({}, S.vtx);
    if (S.spec.vtx && S.phase === "play") {
      if (vtx.phase === "idle") {
        vtx.cool -= dt;
        if (vtx.cool <= 0) {
          vtx.phase = "warn";
          vtx.timer = 1.2 * diff().warn;
          vtx.x = rand(n.w * 0.1, n.w * 0.9);
          vtx.hitDone = false;
          n.banner = { text: "VTX", ttl: 1.2 };
          beep(660, 0.12, "square");
        }
      } else if (vtx.phase === "warn") {
        vtx.timer -= dt;
        if (vtx.timer <= 0) {
          vtx.phase = "fire";
          vtx.timer = 0.6;
          beep(180, 0.3, "sawtooth");
        }
      } else if (vtx.phase === "fire") {
        vtx.timer -= dt;
        if (Math.abs(ship.x - vtx.x) < 20 && ship.respawnWait <= 0) {
          if (!vtx.hitDone) {
            vtx.hitDone = true;
            n.banner = { text: "VTX HIT", ttl: 1.2 };
          }
          if (damageRssi(n, ship, 40 * dt)) {
            burst(parts, ship.x, ship.y, REDUCED ? 1 : 3);
            n.shake = Math.max(n.shake || 0, 6);
          }
        }
        if (vtx.timer <= 0) {
          vtx.phase = "idle";
          vtx.cool = 6;
        }
      }
    }
    n.vtx = vtx;

    // Preamble puncturing: transient notches that destroy packets.
    n.punctures = [];
    S.punctures.forEach(function (pu) {
      var ttl = pu.ttl - dt;
      if (ttl > 0) {
        n.punctures.push({ x: pu.x, w: pu.w, ttl: ttl });
      }
    });
    if (S.spec.punct && S.phase === "play") {
      n.punctCool = (S.punctCool || 0) - dt;
      if (n.punctCool <= 0) {
        n.punctCool = 5;
        var pcount = 1 + ((Math.random() * 2) | 0);
        var pi;
        for (pi = 0; pi < pcount; pi++) {
          n.punctures.push({ x: rand(40, n.w - 40), w: rand(18, 30), ttl: 2.5 });
        }
      }
    }
    if (n.punctures.length) {
      n.packets = n.packets.filter(function (p) {
        var dead = n.punctures.some(function (pu) {
          return Math.abs(p.x - pu.x) < pu.w / 2;
        });
        if (dead) {
          burst(parts, p.x, p.y, 4);
        }
        return !dead;
      });
    }

    n.packets.forEach(function (p) {
      var hit = -1;
      var i;
      for (i = 0; i < rocks.length; i++) {
        var rr = TIER_R[rocks[i].tier] + 3;
        if (dist2(p.x, p.y, rocks[i].x, rocks[i].y) < rr * rr) {
          hit = i;
          break;
        }
      }
      if (hit < 0) {
        livePackets.push(p);
        return;
      }
      var rock = rocks[hit];
      rocks = rocks.slice(0, hit).concat(rocks.slice(hit + 1));
      hits++;
      kills++;
      var mult = 1 + Math.min(combo, 20) * 0.1;
      var gain = Math.round(TIER_SCORE[rock.tier] * mult);
      score += gain;
      gains = gains.concat([{ t: n.t, g: gain }]);
      combo++;
      burst(parts, rock.x, rock.y, 6 + rock.tier * 5);
      if (rock.tier > 0) {
        var i2;
        for (i2 = 0; i2 < 2; i2++) {
          var sa = rand(0, TAU);
          var ss = Math.sqrt(rock.vx * rock.vx + rock.vy * rock.vy) * 1.4 + 26;
          rocks = rocks.concat([{
            x: rock.x, y: rock.y,
            vx: Math.cos(sa) * ss, vy: Math.sin(sa) * ss,
            tier: rock.tier - 1, seed: Math.random() * 1000, name: rock.name
          }]);
        }
      }
      // Destroyed interference drops power-ups. The drop table is band-aware
      // (no 160 MHz on 2.4, no 320 MHz below 6 GHz).
      if (Math.random() < 0.18) {
        var pa = rand(0, TAU);
        n.powers.push({
          x: rock.x, y: rock.y,
          vx: Math.cos(pa) * 24, vy: Math.sin(pa) * 24,
          kind: pick(dropTable(n.band)), ttl: 9
        });
      }
      beep(660 + rock.tier * 120, 0.06, "square");
    });
    n.packets = livePackets;
    n.rocks = rocks;
    n.kills = kills;
    n.hits = hits;
    n.score = score;
    n.gains = gains;
    // Damage earlier this tick wins over kills later in it.
    n.combo = n.comboReset ? 0 : combo;
    delete n.comboReset;
    n.parts = parts.filter(function (p) {
      p.life -= dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      return p.life > 0;
    }).slice(-200);

    // Ship vs rock: RSSI damage, never instant death.
    if (ship.invuln <= 0 && ship.respawnWait <= 0) {
      rocks.forEach(function (r) {
        var rr = TIER_R[r.tier] + 10;
        if (dist2(r.x, r.y, ship.x, ship.y) < rr * rr) {
          damageRssi(n, ship, 12);
          ship.invuln = Math.max(ship.invuln, 0.5);
          burst(parts, ship.x, ship.y, 14);
          n.shake = 8;
          beep(140, 0.2, "sawtooth");
        }
      });
    }

    // Deauth vs ship: PMF drops the frame in flight, otherwise heavy damage.
    var keptDeauth2 = [];
    n.deauths.forEach(function (d) {
      if (fx.pmf > 0 && ship.respawnWait <= 0 && dist2(d.x, d.y, ship.x, ship.y) < PMF_R * PMF_R) {
        burst(parts, d.x, d.y, REDUCED ? 2 : 6);
        n.pmfKills = (n.pmfKills || 0) + 1;
        beep(1046, 0.04, "square");
        return;
      }
      if (ship.invuln <= 0 && ship.respawnWait <= 0 && dist2(d.x, d.y, ship.x, ship.y) < 14 * 14) {
        damageRssi(n, ship, 8);
        burst(parts, ship.x, ship.y, 10);
        n.shake = 6;
      } else {
        keptDeauth2.push(d);
      }
    });
    n.deauths = keptDeauth2;

    // Shield break: the WPA3 ring popped on the absorbed hit.
    if (n.shieldDropped) {
      n.shieldDropped = false;
      n.shieldDropT = 0.6;
      n.banner = { text: "WPA3 SHIELD DOWN", ttl: 1.3 };
      burst(parts, ship.x, ship.y, REDUCED ? 4 : 18);
      n.shake = Math.max(n.shake || 0, 7);
      beep(300, 0.2, "sawtooth");
    }
    n.shieldDropT = Math.max(0, (n.shieldDropT || 0) - dt);

    // RSSI decay, proximity, recovery.
    if (fx.wpa3 <= 0) {
      var nearest = Infinity;
      rocks.forEach(function (r) {
        var d = Math.sqrt(dist2(r.x, r.y, ship.x, ship.y));
        if (d < nearest) {
          nearest = d;
        }
      });
      var decay = 1.1 * (1 + n.noise * 2);
      if (nearest < 110) {
        decay += (1 - nearest / 110) * 6;
      }
      if (inZone(ship.x)) {
        decay *= 1.8;
      }
      ship.rssi -= decay * diff().rssiDecay * dt;
      if (nearest > 150 && !inZone(ship.x)) {
        ship.rssi += 3 * dt;
      }
      if (ship.rssi > -30) {
        ship.rssi = -30;
      }
    }

    // Link drop at -90 costs a retry.
    if (ship.rssi <= -90) {
      ship.retries -= 1;
      ship.rssi = -50;
      ship.respawnWait = 1.2;
      n.combo = 0;
      burst(parts, ship.x, ship.y, 26);
      n.shake = 12;
      n.banner = { text: ship.retries >= 0 ? "LINK DROPPED, RETRYING" : "LINK DROPPED", ttl: 1.8 };
      beep(110, 0.35, "sawtooth");
      if (ship.retries < 0) {
        return gameOver(n);
      }
    }

    // Level clear: every interference source destroyed.
    if (n.rocks.length === 0 && n.phase === "play") {
      var bonus = Math.round((ship.rssi + 90) * 1.5);
      n.score = n.score + bonus;
      n.clearBonus = bonus;
      n.phase = "clear";
      n.clearTimer = CLEAR_DUR;
      n.banner = { text: "", ttl: 0 };
      beep(1046, 0.12, "sine");
      if (n.score > store.high) {
        store.high = Math.round(n.score);
        saveStore();
      }
    }

    if (n.banner.ttl > 0) {
      n.banner = { text: n.banner.text, ttl: n.banner.ttl - dt };
    }
    if (n.hint && n.hint.ttl > 0) {
      n.hint = { text: n.hint.text, ttl: n.hint.ttl - dt };
    }
    n.shake = Math.max(0, (n.shake || 0) - 30 * dt);
    return n;
  }

  function damageRssi(n, ship, amount) {
    if (n.fx.wpa3 > 0) {
      // Shield eats the hit, then drops.
      n.fx.wpa3 = 0;
      n.shieldDropped = true;
      n.combo = 0;
      n.comboReset = true;
      return false;
    }
    ship.rssi -= amount;
    // Kills later in the same tick must not resurrect the combo.
    n.combo = 0;
    n.comboReset = true;
    return true;
  }

  function burst(parts, x, y, count) {
    if (REDUCED) {
      count = Math.min(4, count);
    }
    var i;
    for (i = 0; i < count; i++) {
      var a = rand(0, TAU);
      var sp = rand(30, 160);
      parts.push({ x: x, y: y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: rand(0.3, 0.8), max: 0.8 });
    }
  }

  var POWER_NAMES = { "40": "40MHz", "80": "80MHz", "160": "160MHz", "320": "320MHz", "MU": "MU-MIMO", "BF": "Beamforming", "W3": "WPA3", "W2": "WPA2", "CSA": "Channel switch", "PMF": "PMF shield" };
  function applyPowerup(n, kind) {
    if (SPREAD[kind]) {
      n.fx.spread = 10;
      n.fx.spreadKind = kind;
    } else if (kind === "MU") {
      n.fx.mimo = Math.max(n.fx.mimo, 10);
      // Spatial diversity angle is rolled once per pickup.
      n.fx.mimoAngle = pickMimoAngle();
    } else if (kind === "BF") {
      n.fx.beam = Math.max(n.fx.beam, 10);
    } else if (kind === "W3") {
      n.fx.wpa3 = Math.max(n.fx.wpa3, 10);
    } else if (kind === "PMF") {
      n.fx.pmf = Math.max(n.fx.pmf, 10);
    } else if (kind === "W2") {
      // Negative booster: WPA2 lets rogues beamform their deauth frames.
      n.fx.wpa2 = Math.max(n.fx.wpa2, 10);
      n.banner = { text: "WPA2 DOWNGRADE, ROGUES LOCK ON", ttl: 1.8 };
      return;
    } else if (kind === "CSA") {
      n.zones = [];
    }
    n.banner = { text: POWER_NAMES[kind] + " ACQUIRED", ttl: 1.4 };
  }

  function gameOver(n) {
    var peak = 0;
    var i, j, sum;
    var gains = n.gains;
    for (i = 0; i < gains.length; i++) {
      sum = 0;
      for (j = i; j < gains.length && gains[j].t - gains[i].t < 3; j++) {
        sum += gains[j].g;
      }
      if (sum > peak) {
        peak = sum;
      }
    }
    var avg = n.uptime > 0 ? n.score / n.uptime : 0;
    var loss = n.sent > 0 ? (1 - (n.hits || 0) / n.sent) * 100 : 0;
    if (n.score > store.high) {
      store.high = Math.round(n.score);
      saveStore();
    }
    var over = Object.assign({}, n);
    over.phase = "over";
    over.over = {
      peak: peak / 3, avg: avg, sent: n.sent, loss: loss,
      uptime: n.uptime, score: Math.round(n.score), level: n.level
    };
    return over;
  }

  // Nominate one top-level state reference; update returns the next.
  var S = initialState(stage.clientWidth || 640, stage.clientHeight || 400);

  // ---- Render: the only place that mutates anything besides S ------------
  var hudTimer = -1;
  var hudCache = {};
  function setHud(id, text) {
    if (hudCache[id] === text) {
      return;
    }
    hudCache[id] = text;
    var el = document.getElementById(id);
    if (el) {
      el.textContent = text;
    }
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // A centred Bluetooth rune of the given size (feather glyph scaled).
  function drawBtRune(ctx, size) {
    var k = size / 24;
    ctx.save();
    ctx.scale(k, k);
    ctx.translate(-12, -12);
    ctx.beginPath();
    ctx.moveTo(6.5, 6.5);
    ctx.lineTo(17.5, 17.5);
    ctx.lineTo(12, 23);
    ctx.lineTo(12, 1);
    ctx.lineTo(17.5, 6.5);
    ctx.lineTo(6.5, 17.5);
    ctx.stroke();
    ctx.restore();
  }

  // The largest interference source is drawn as a recognizable device that
  // matches its label; its fragments stay classic asteroids.
  function drawSourceShape(ctx, name, x, y, R) {
    ctx.save();
    ctx.translate(x, y);
    ctx.lineWidth = 1.6;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = THEME.text;
    ctx.fillStyle = THEME.text;
    var i, j;
    if (name === "MICROWAVE") {
      var mw = R * 1.5;
      var mh = R * 0.95;
      ctx.strokeRect(-mw / 2, -mh / 2, mw, mh);
      ctx.strokeRect(-mw / 2 + 3, -mh / 2 + 3, mw * 0.58, mh - 6);
      ctx.beginPath();
      ctx.moveTo(-mw / 2 + 5, -2);
      ctx.lineTo(-mw / 2 + 3 + mw * 0.58 - 2, -2);
      ctx.moveTo(-mw / 2 + 5, 2);
      ctx.lineTo(-mw / 2 + 3 + mw * 0.58 - 2, 2);
      ctx.stroke();
      for (i = -1; i <= 1; i++) {
        ctx.beginPath();
        ctx.arc(mw / 2 - 7, i * (mh / 4), 1.6, 0, TAU);
        ctx.fill();
      }
    } else if (name === "BABY MONITOR") {
      var bw = R * 1.15;
      var bh = R * 0.9;
      roundRect(ctx, -bw / 2, -bh / 2, bw, bh, 4);
      ctx.stroke();
      ctx.strokeRect(-bw / 2 + 3, -bh / 2 + 3, bw - 6, bh - 12);
      ctx.beginPath();
      ctx.moveTo(bw / 2 - 5, -bh / 2);
      ctx.lineTo(bw / 2 + 2, -bh / 2 - 11);
      ctx.moveTo(-bw / 4, bh / 2);
      ctx.lineTo(-bw / 4, bh / 2 + 5);
      ctx.moveTo(bw / 4, bh / 2);
      ctx.lineTo(bw / 4, bh / 2 + 5);
      ctx.stroke();
    } else if (name === "CORDLESS PHONE") {
      var pw = R * 0.62;
      var ph = R * 1.25;
      roundRect(ctx, -pw / 2, -ph / 2, pw, ph, 5);
      ctx.stroke();
      ctx.strokeRect(-pw / 2 + 3, -ph / 2 + 4, pw - 6, ph * 0.2);
      for (j = 0; j < 3; j++) {
        for (i = 0; i < 3; i++) {
          ctx.beginPath();
          ctx.arc(-pw / 2 + 5 + (i * (pw - 10)) / 2, ph * 0.02 + j * 7, 1.1, 0, TAU);
          ctx.fill();
        }
      }
    } else if (name === "BT CLUSTER") {
      drawBtRune(ctx, R * 1.0);
      var spots = [[-R * 0.78, -R * 0.52], [R * 0.74, -R * 0.44], [0, R * 0.84]];
      for (i = 0; i < spots.length; i++) {
        ctx.save();
        ctx.translate(spots[i][0], spots[i][1]);
        drawBtRune(ctx, R * 0.52);
        ctx.restore();
      }
    } else if (name === "FPV DRONE") {
      var arm = R * 0.62;
      ctx.beginPath();
      ctx.moveTo(-arm, -arm);
      ctx.lineTo(arm, arm);
      ctx.moveTo(arm, -arm);
      ctx.lineTo(-arm, arm);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(0, 0, R * 0.2, 0, TAU);
      ctx.fill();
      var corners = [[-arm, -arm], [arm, -arm], [-arm, arm], [arm, arm]];
      for (i = 0; i < corners.length; i++) {
        ctx.beginPath();
        ctx.arc(corners[i][0], corners[i][1], R * 0.22, 0, TAU);
        ctx.stroke();
      }
    } else if (name === "RF JAMMER") {
      var jw = R * 1.1;
      var jh = R * 0.8;
      roundRect(ctx, -jw / 2, -jh / 2, jw, jh, 3);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, -jh / 2);
      ctx.lineTo(0, -jh / 2 - R * 0.5);
      ctx.stroke();
      for (i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.arc(0, -jh / 2 - R * 0.5, R * 0.18 + i * R * 0.16, -Math.PI * 0.85, -Math.PI * 0.15);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(-jw * 0.25, jh * 0.1, 1.4, 0, TAU);
      ctx.arc(jw * 0.25, jh * 0.1, 1.4, 0, TAU);
      ctx.fill();
    } else if (name === "VIDEO CAMERA") {
      var cw = R * 1.4;
      var ch = R * 0.85;
      roundRect(ctx, -cw / 2, -ch / 2, cw * 0.72, ch, 3);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(cw * 0.36, 0, R * 0.26, 0, TAU);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(-cw / 2, -ch * 0.15);
      ctx.lineTo(-cw / 2 - R * 0.28, -ch * 0.4);
      ctx.lineTo(-cw / 2 - R * 0.28, ch * 0.1);
      ctx.lineTo(-cw / 2, ch * 0.25);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(-cw * 0.16, -ch / 2);
      ctx.lineTo(-cw * 0.16, -ch / 2 - R * 0.18);
      ctx.lineTo(cw * 0.1, -ch / 2 - R * 0.18);
      ctx.lineTo(cw * 0.1, -ch / 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function render(S) {
    ctx.save();
    ctx.fillStyle = THEME.page;
    ctx.fillRect(0, 0, S.w, S.h);
    if (!REDUCED && S.shake > 0) {
      ctx.translate(rand(-S.shake, S.shake) * 0.5, rand(-S.shake, S.shake) * 0.5);
    }

    // Congestion zones: translucent drifting bands. Labeled so it is clear
    // what the moving bars are, and what they do.
    S.zones.forEach(function (z) {
      ctx.fillStyle = "rgba(244, 86, 37, 0.10)";
      ctx.fillRect(z.x - z.w / 2, 0, z.w, S.h);
      ctx.strokeStyle = "rgba(244, 86, 37, 0.4)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(z.x - z.w / 2, 0);
      ctx.lineTo(z.x - z.w / 2, S.h);
      ctx.moveTo(z.x + z.w / 2, 0);
      ctx.lineTo(z.x + z.w / 2, S.h);
      ctx.stroke();
      ctx.fillStyle = "rgba(244, 86, 37, 0.85)";
      ctx.font = "9px " + THEME.mono;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      var zoneLabelX = Math.max(30, Math.min(S.w - 30, z.x));
      ctx.fillText("CONGESTION", zoneLabelX, S.h / 2);
    });

    // Preamble puncturing: narrow notches that destroy packets.
    S.punctures.forEach(function (pu) {
      var px0 = pu.x - pu.w / 2;
      ctx.fillStyle = "rgba(2, 119, 189, 0.14)";
      ctx.fillRect(px0, 0, pu.w, S.h);
      ctx.save();
      ctx.beginPath();
      ctx.rect(px0, 0, pu.w, S.h);
      ctx.clip();
      ctx.strokeStyle = "rgba(2, 119, 189, 0.3)";
      ctx.lineWidth = 1;
      var ph;
      for (ph = -S.h; ph < S.w + S.h; ph += 12) {
        ctx.beginPath();
        ctx.moveTo(ph, 0);
        ctx.lineTo(ph + S.h, S.h);
        ctx.stroke();
      }
      ctx.restore();
      ctx.strokeStyle = "rgba(2, 119, 189, 0.5)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(px0, 0);
      ctx.lineTo(px0, S.h);
      ctx.moveTo(px0 + pu.w, 0);
      ctx.lineTo(px0 + pu.w, S.h);
      ctx.stroke();
      ctx.fillStyle = "rgba(2, 119, 189, 0.9)";
      ctx.font = "8px " + THEME.mono;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText("PUNCTURED", pu.x, 6);
    });

    // DFS sweep band. It enters from the side opposite the ship, so the
    // swept side is live and the unswept side is still safe.
    if (S.dfs.active > 0) {
      var dfsProg = 1 - Math.max(0, S.dfs.active) / DFS_DUR;
      var dfsFront = S.dfs.dir > 0 ? dfsProg * S.w : (1 - dfsProg) * S.w;
      var dangerX = S.dfs.dir > 0 ? 0 : dfsFront;
      var dangerW = S.dfs.dir > 0 ? dfsFront : S.w - dfsFront;
      ctx.fillStyle = "rgba(211, 47, 47, 0.20)";
      ctx.fillRect(dangerX, S.dfs.y - 34, dangerW, 68);
      // Hatched, so the damaging sweep reads differently from congestion.
      ctx.save();
      ctx.beginPath();
      ctx.rect(dangerX, S.dfs.y - 34, dangerW, 68);
      ctx.clip();
      ctx.strokeStyle = "rgba(211, 47, 47, 0.35)";
      ctx.lineWidth = 1;
      var hatch;
      for (hatch = dangerX - 68; hatch < dangerX + dangerW + 68; hatch += 10) {
        ctx.beginPath();
        ctx.moveTo(hatch, S.dfs.y - 34);
        ctx.lineTo(hatch + 68, S.dfs.y + 34);
        ctx.stroke();
      }
      ctx.restore();
      ctx.strokeStyle = "rgba(211, 47, 47, 0.4)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, S.dfs.y - 34);
      ctx.lineTo(S.w, S.dfs.y - 34);
      ctx.moveTo(0, S.dfs.y + 34);
      ctx.lineTo(S.w, S.dfs.y + 34);
      ctx.stroke();
      ctx.strokeStyle = THEME.danger;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(dfsFront, S.dfs.y - 40);
      ctx.lineTo(dfsFront, S.dfs.y + 40);
      ctx.stroke();
      ctx.fillStyle = THEME.danger;
      ctx.font = "9px " + THEME.mono;
      ctx.textBaseline = "middle";
      if (S.dfs.dir > 0) {
        ctx.textAlign = "left";
        ctx.fillText("RADAR", 4, S.dfs.y - 42);
      } else {
        ctx.textAlign = "right";
        ctx.fillText("RADAR", S.w - 4, S.dfs.y - 42);
      }
    }

    // AFC: stationary announced/locked band (6 GHz coordination).
    if (S.afc && S.afc.phase !== "idle") {
      var ay = S.afc.y;
      if (S.afc.phase === "warn") {
        ctx.strokeStyle = THEME.danger;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 6]);
        ctx.beginPath();
        ctx.moveTo(0, ay - 30);
        ctx.lineTo(S.w, ay - 30);
        ctx.moveTo(0, ay + 30);
        ctx.lineTo(S.w, ay + 30);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = THEME.danger;
        ctx.font = "9px " + THEME.mono;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText("AFC CHECK", 4, ay - 36);
      } else {
        ctx.fillStyle = "rgba(211, 47, 47, 0.20)";
        ctx.fillRect(0, ay - 30, S.w, 60);
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, ay - 30, S.w, 60);
        ctx.clip();
        ctx.strokeStyle = "rgba(211, 47, 47, 0.35)";
        ctx.lineWidth = 1;
        var ah;
        for (ah = -60; ah < S.w + 60; ah += 10) {
          ctx.beginPath();
          ctx.moveTo(ah, ay - 30);
          ctx.lineTo(ah + 60, ay + 30);
          ctx.stroke();
        }
        ctx.restore();
        ctx.fillStyle = THEME.danger;
        ctx.font = "9px " + THEME.mono;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText("AFC LOCKED", 4, ay - 36);
      }
    }

    // VTX: a carrier spike on a spectrum analyzer, with noise shoulders.
    if (S.vtx && S.vtx.phase !== "idle") {
      var vx = S.vtx.x;
      if (S.vtx.phase === "warn") {
        ctx.strokeStyle = THEME.danger;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 6]);
        ctx.beginPath();
        ctx.moveTo(vx, 0);
        ctx.lineTo(vx, S.h);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = THEME.danger;
        ctx.font = "9px " + THEME.mono;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillText("VTX", vx, 4);
      } else {
        ctx.fillStyle = "rgba(211, 47, 47, 0.14)";
        ctx.fillRect(vx - 22, 0, 44, S.h);
        if (!REDUCED) {
          ctx.fillStyle = THEME.danger;
          ctx.globalAlpha = 0.25;
          var sd;
          for (sd = 0; sd < 70; sd++) {
            ctx.fillRect(vx - 22 + Math.random() * 44, Math.random() * S.h, 1.5, 1.5);
          }
          ctx.globalAlpha = 1;
        }
        ctx.strokeStyle = THEME.danger;
        ctx.lineWidth = 6;
        ctx.globalAlpha = 0.35;
        ctx.beginPath();
        ctx.moveTo(vx, 0);
        ctx.lineTo(vx, S.h);
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(vx, 0);
        ctx.lineTo(vx, S.h);
        ctx.stroke();
      }
    }

    // Noise floor static.
    if (!REDUCED && S.noise > 0.05) {
      ctx.fillStyle = THEME.text;
      var dots = Math.round(S.noise * 46);
      var i;
      for (i = 0; i < dots; i++) {
        ctx.globalAlpha = 0.16;
        ctx.fillRect(Math.random() * S.w, Math.random() * S.h, 1.5, 1.5);
      }
      ctx.globalAlpha = 1;
    }

    // Power-ups with ttl countdown ring.
    S.powers.forEach(function (pu) {
      ctx.strokeStyle = THEME.info;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(pu.x, pu.y, 11, 0, TAU);
      ctx.stroke();
      ctx.strokeStyle = THEME.brand;
      ctx.beginPath();
      ctx.arc(pu.x, pu.y, 14, -Math.PI / 2, -Math.PI / 2 + TAU * (pu.ttl / 9));
      ctx.stroke();
      ctx.fillStyle = THEME.text;
      ctx.font = "9px " + THEME.mono;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(pu.kind, pu.x, pu.y);
    });

    // Packets: RF wavefronts travelling in the shot direction, not bullets.
    S.packets.forEach(function (p) {
      var col = p.ghost ? THEME.info : THEME.brand;
      var ang = Math.atan2(p.vy, p.vx);
      ctx.strokeStyle = col;
      ctx.lineCap = "round";
      ctx.globalAlpha = 0.25;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(p.x - p.vx * 0.05, p.y - p.vy * 0.05);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(ang);
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.arc(-4, 0, 4.5, -0.7, 0.7);
      ctx.stroke();
      ctx.globalAlpha = 0.6;
      ctx.beginPath();
      ctx.arc(-4, 0, 8, -0.55, 0.55);
      ctx.stroke();
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.arc(-4, 0, 11.5, -0.45, 0.45);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.restore();
    });

    // Interference sources: the largest is a device matching its label;
    // fragments stay classic asteroid polygons.
    S.rocks.forEach(function (r) {
      var R = TIER_R[r.tier];
      if (r.tier === 2) {
        drawSourceShape(ctx, r.name, r.x, r.y, R);
      } else {
        ctx.strokeStyle = THEME.text;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        var k;
        for (k = 0; k < 8; k++) {
          var aa = (k / 8) * TAU + r.seed;
          var rr = R * (0.78 + 0.3 * Math.abs(Math.sin(r.seed * (k + 2))));
          var px = r.x + Math.cos(aa) * rr;
          var py = r.y + Math.sin(aa) * rr;
          if (k === 0) {
            ctx.moveTo(px, py);
          } else {
            ctx.lineTo(px, py);
          }
        }
        ctx.closePath();
        ctx.stroke();
      }
    });

    // Rogue APs with fake SSID labels, and their deauth frames.
    S.rogues.forEach(function (g) {
      ctx.lineWidth = 1.6;
      var i;
      if (g.mlo) {
        // MLO rogue: two interlocked links, one red and one orange.
        var lr = 7;
        var lx = 5;
        ctx.strokeStyle = THEME.danger;
        ctx.beginPath();
        ctx.arc(g.x - lx, g.y, lr, 0, TAU);
        ctx.stroke();
        ctx.strokeStyle = THEME.brand;
        ctx.beginPath();
        ctx.arc(g.x + lx, g.y, lr, 0, TAU);
        ctx.stroke();
        for (i = 0; i < 3; i++) {
          ctx.strokeStyle = THEME.danger;
          ctx.beginPath();
          ctx.arc(g.x - lx, g.y, 3 + i * 3, -Math.PI * 0.9, -Math.PI * 0.1);
          ctx.stroke();
          ctx.strokeStyle = THEME.brand;
          ctx.beginPath();
          ctx.arc(g.x + lx, g.y, 3 + i * 3, -Math.PI * 0.9, -Math.PI * 0.1);
          ctx.stroke();
        }
      } else {
        ctx.strokeStyle = THEME.danger;
        for (i = 0; i < 3; i++) {
          ctx.beginPath();
          ctx.arc(g.x, g.y, 6 + i * 6, -Math.PI * 0.8, -Math.PI * 0.2);
          ctx.stroke();
        }
        ctx.fillStyle = THEME.danger;
        ctx.beginPath();
        ctx.arc(g.x, g.y, 2.5, 0, TAU);
        ctx.fill();
      }
      ctx.fillStyle = g.mlo ? THEME.brand : THEME.danger;
      ctx.font = "9px " + THEME.mono;
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(g.ssid, g.x, g.y - 30);
    });
    S.deauths.forEach(function (d) {
      ctx.strokeStyle = THEME.danger;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(d.x - 5, d.y - 4);
      ctx.lineTo(d.x, d.y);
      ctx.lineTo(d.x - 5, d.y + 4);
      ctx.moveTo(d.x + 1, d.y - 4);
      ctx.lineTo(d.x + 6, d.y);
      ctx.lineTo(d.x + 1, d.y + 4);
      ctx.stroke();
    });

    // Ship: client device with antenna glyph, thrust as signal arcs.
    var ship = S.ship;
    if (ship.respawnWait <= 0) {
      var blink = ship.invuln > 0 && ((S.t * 8) | 0) % 2 === 0;
      if (!blink) {
        if (ship.thrusting && !REDUCED) {
          ctx.strokeStyle = THEME.brand;
          ctx.lineWidth = 1.5;
          var w;
          for (w = 0; w < 2; w++) {
            var wr = 14 + ((S.t * 60 + w * 12) % 18);
            ctx.globalAlpha = 1 - wr / 36;
            ctx.beginPath();
            ctx.arc(
              ship.x - Math.cos(ship.a) * 10, ship.y - Math.sin(ship.a) * 10,
              wr, ship.a + Math.PI - 0.5, ship.a + Math.PI + 0.5
            );
            ctx.stroke();
          }
          ctx.globalAlpha = 1;
        }
        ctx.strokeStyle = THEME.text;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(ship.x + Math.cos(ship.a) * 14, ship.y + Math.sin(ship.a) * 14);
        ctx.lineTo(ship.x + Math.cos(ship.a + 2.5) * 11, ship.y + Math.sin(ship.a + 2.5) * 11);
        ctx.lineTo(ship.x + Math.cos(ship.a - 2.5) * 11, ship.y + Math.sin(ship.a - 2.5) * 11);
        ctx.closePath();
        ctx.stroke();
        // Antenna glyph.
        ctx.beginPath();
        ctx.moveTo(ship.x, ship.y);
        ctx.lineTo(ship.x - Math.cos(ship.a) * 7, ship.y - Math.sin(ship.a) * 7);
        ctx.stroke();
        ctx.fillStyle = THEME.brand;
        ctx.beginPath();
        ctx.arc(ship.x - Math.cos(ship.a) * 7, ship.y - Math.sin(ship.a) * 7, 2, 0, TAU);
        ctx.fill();
      }
      // WPA3 shield: a pulsing ring that eats one hit, then pops.
      if (S.fx.wpa3 > 0) {
        var shieldR = 17 + Math.sin(S.t * 6) * 1.5;
        ctx.strokeStyle = THEME.ok;
        ctx.lineWidth = 2.5;
        ctx.globalAlpha = 0.85;
        ctx.beginPath();
        ctx.arc(ship.x, ship.y, shieldR, 0, TAU);
        ctx.stroke();
        ctx.globalAlpha = 0.35;
        ctx.beginPath();
        ctx.arc(ship.x, ship.y, shieldR + 4, 0, TAU);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      if (S.shieldDropT > 0) {
        var shieldProg = 1 - S.shieldDropT / 0.6;
        ctx.strokeStyle = THEME.ok;
        ctx.lineWidth = 3;
        ctx.globalAlpha = Math.max(0, 1 - shieldProg);
        ctx.beginPath();
        ctx.arc(ship.x, ship.y, 18 + shieldProg * 34, 0, TAU);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      // PMF: a rotating dashed field that drops management frames in flight.
      if (S.fx.pmf > 0) {
        ctx.strokeStyle = THEME.info;
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = 0.55;
        ctx.setLineDash([4, 4]);
        ctx.lineDashOffset = -S.t * 24;
        ctx.beginPath();
        ctx.arc(ship.x, ship.y, PMF_R, 0, TAU);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.lineDashOffset = 0;
        ctx.globalAlpha = 1;
      }
    }

    // Explosion particles.
    S.parts.forEach(function (p) {
      ctx.globalAlpha = Math.max(0, p.life / p.max);
      ctx.fillStyle = THEME.brand;
      ctx.fillRect(p.x, p.y, 2, 2);
    });
    ctx.globalAlpha = 1;

    // Banners and pause text.
    if (S.banner.ttl > 0 && S.banner.text) {
      ctx.fillStyle = THEME.text;
      ctx.font = "16px " + THEME.mono;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(S.banner.text, S.w / 2, S.h * 0.3);
    }
    if (S.phase === "clear") {
      var panelW = Math.min(340, S.w - 32);
      var panelH = 168;
      var px0 = (S.w - panelW) / 2;
      var py0 = (S.h - panelH) / 2;
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      ctx.fillRect(0, 0, S.w, S.h);
      ctx.fillStyle = THEME.surface;
      ctx.fillRect(px0, py0, panelW, panelH);
      ctx.strokeStyle = THEME.brand;
      ctx.lineWidth = 2;
      ctx.strokeRect(px0, py0, panelW, panelH);
      ctx.fillStyle = THEME.text;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "18px " + THEME.mono;
      ctx.fillText("LEVEL " + S.level + " CLEAR", S.w / 2, py0 + 34);
      ctx.font = "14px " + THEME.mono;
      ctx.fillText("airtime reclaimed +" + fmtAirtime(S.clearBonus || 0), S.w / 2, py0 + 68);
      var nextSpec = levelSpec(S.level + 1);
      ctx.fillText("next: " + nextSpec.band + " / ch " + nextSpec.ch, S.w / 2, py0 + 98);
      var clearProg = 1 - Math.max(0, S.clearTimer) / CLEAR_DUR;
      ctx.fillStyle = THEME.border;
      ctx.fillRect(px0 + 24, py0 + 128, panelW - 48, 8);
      ctx.fillStyle = THEME.brand;
      ctx.fillRect(px0 + 24, py0 + 128, (panelW - 48) * clearProg, 8);
    }
    if (S.paused && S.phase === "play") {
      ctx.fillStyle = THEME.text;
      ctx.font = "15px " + THEME.mono;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("PAUSED, P TO RESUME", S.w / 2, S.h / 2);
    }
    ctx.restore();

    // HUD in the DOM, throttled. A restart resets game time, so re-arm the
    // throttle whenever it runs backwards or the header would stay stale.
    if (S.t <= hudTimer) {
      hudTimer = -1;
    }
    if (S.t - hudTimer > 0.1) {
      hudTimer = S.t;
      var link = LINK_RATES[Math.min(S.combo, LINK_RATES.length - 1)];
      var fxBits = [];
      if (S.fx.spread > 0) {
        fxBits.push((S.fx.spreadKind || "40") + "MHz " + Math.ceil(S.fx.spread) + "s");
      }
      if (S.fx.mimo > 0) {
        fxBits.push("MU-MIMO " + Math.ceil(S.fx.mimo) + "s");
      }
      if (S.fx.beam > 0) {
        fxBits.push("Beamforming " + Math.ceil(S.fx.beam) + "s");
      }
      if (S.fx.wpa3 > 0) {
        fxBits.push("WPA3 shield " + Math.ceil(S.fx.wpa3) + "s");
      }
      if (S.fx.pmf > 0) {
        fxBits.push("PMF shield " + Math.ceil(S.fx.pmf) + "s");
      }
      if (S.fx.wpa2 > 0) {
        fxBits.push("WPA2 " + Math.ceil(S.fx.wpa2) + "s");
      }
      setHud("ps-score", fmtAirtime(S.score) + " airtime");
      setHud("ps-rssi", Math.round(S.ship.rssi) + " dBm");
      setHud("ps-retries", "retries " + Math.max(0, S.ship.retries));
      setHud("ps-level", "level " + S.level);
      setHud("ps-band", S.band + " / ch " + S.ch);
      setHud("ps-link", "link " + link + "M");
      setHud("ps-fx", fxBits.join("  "));
      setHud("ps-diff", S.diff || "normal");
      setHud("ps-high", "best " + fmtAirtime(store.high));
      setHud("ps-hint", S.hint && S.hint.ttl > 0 ? S.hint.text : "");
      var bar = document.getElementById("ps-rssibar");
      if (bar) {
        var pct = Math.max(0, Math.min(100, ((S.ship.rssi + 90) / 60) * 100));
        bar.style.width = pct + "%";
      }
    }
  }

  // ---- HUD and overlay DOM ----------------------------------------------
  hud.innerHTML =
    '<span id="ps-score"></span>' +
    '<span><span id="ps-rssibar-wrap"><span id="ps-rssibar"></span></span> <span id="ps-rssi"></span></span>' +
    '<span id="ps-retries"></span>' +
    '<span id="ps-level"></span>' +
    '<span id="ps-band"></span>' +
    '<span id="ps-link"></span>' +
    '<span id="ps-fx"></span>' +
    '<span id="ps-diff"></span>' +
    '<span id="ps-high"></span>' +
    '<span id="ps-hint"></span>';
  var overlay = document.createElement("div");
  overlay.id = "packetstorm-over";
  overlay.setAttribute("style", "display:none;position:absolute;inset:0;align-items:center;" +
    "justify-content:center;background:rgba(0,0,0,0.55);");
  overlay.innerHTML = '<div id="ps-overbox"></div>';
  stage.appendChild(overlay);

  // HUD and overlays read the theme tokens, and are refreshed on theme change.
  function applyChrome() {
    // Leave room on the right for the shared Exit button.
    hud.setAttribute("style",
      "position:absolute;top:8px;left:10px;right:4rem;display:flex;flex-wrap:wrap;" +
      "gap:4px 14px;font-family:" + THEME.mono + ";font-size:12px;color:" + THEME.text + ";" +
      "pointer-events:none;text-shadow:0 1px 2px rgba(0,0,0,0.35);");
    var box = document.getElementById("ps-overbox");
    if (box) {
      box.setAttribute("style",
        "font-family:" + THEME.mono + ";color:" + THEME.text +
        ";background:" + THEME.surface + ";border:2px solid " + THEME.border +
        ";border-radius:6px;padding:20px 26px;text-align:center;line-height:1.7;");
    }
  }
  applyChrome();

  function showOver(o) {
    var box = document.getElementById("ps-overbox");
    if (!box) {
      return;
    }
    box.innerHTML =
      "Link report<br>" +
      "Airtime reclaimed: " + fmtAirtime(o.score) + "<br>" +
      "Frames sent: " + o.sent + "<br>" +
      "Frame loss: " + o.loss.toFixed(1) + "%<br>" +
      "Uptime: " + Math.round(o.uptime) + " s<br>" +
      "Reached: " + S.band + " / ch " + S.ch + ", level " + o.level + "<br>" +
      "<br>Press Enter or tap to retest";
    overlay.style.display = "flex";
  }
  function hideOver() {
    overlay.style.display = "none";
  }

  // Start sequence: the controls panel holds the game until the first input.
  var help = document.getElementById("packetstorm-help");
  var diffHandlers = [];
  var diffButtons = help ? help.querySelectorAll("[data-diff]") : [];

  function syncDiffButtons() {
    Array.prototype.forEach.call(diffButtons, function (btn) {
      var on = btn.getAttribute("data-diff") === (store.difficulty || "normal");
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", String(on));
    });
  }

  function setDifficulty(mode) {
    store.difficulty = mode === "easy" ? "easy" : "normal";
    saveStore();
    S = initialState(S.w, S.h);
    S.intro = false;
    hideHelp();
    hudTimer = -1;
    try {
      canvas.focus({ preventScroll: true });
    } catch (e) {
      /* ignore */
    }
  }

  Array.prototype.forEach.call(diffButtons, function (btn) {
    var handler = function (e) {
      e.preventDefault();
      setDifficulty(btn.getAttribute("data-diff"));
    };
    btn.addEventListener("click", handler);
    diffHandlers.push([btn, "click", handler]);
  });

  function showHelp() {
    if (help) {
      help.hidden = false;
      syncDiffButtons();
    }
  }
  function hideHelp() {
    if (help) {
      help.hidden = true;
    }
  }
  function startPlay(evt) {
    // Let the difficulty buttons handle their own click; otherwise hiding the
    // panel on pointerdown would swallow it.
    if (evt && evt.target && evt.target.closest && evt.target.closest("[data-diff]")) {
      return;
    }
    if (!S.intro) {
      return;
    }
    S = Object.assign({}, S);
    S.intro = false;
    hideHelp();
    try {
      canvas.focus({ preventScroll: true });
    } catch (e) {
      /* ignore */
    }
  }

  // ---- Canvas sizing: container, DPR, never resets the game -------------
  function fitCanvas() {
    var dpr = window.devicePixelRatio || 1;
    var w = Math.max(200, stage.clientWidth);
    var h = Math.max(200, stage.clientHeight);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    S.w = w;
    S.h = h;
  }
  fitCanvas();

  // ---- Main loop: fixed timestep physics, rAF rendering -----------------
  var raf = 0;
  var last = 0;
  var acc = 0;
  function frame(t) {
    raf = requestAnimationFrame(frame);
    if (last === 0) {
      last = t;
    }
    var dt = (t - last) / 1000;
    last = t;
    if (dt > 0.1) {
      dt = 0.1;
    }
    if (S.paused || S.autoPaused || document.hidden) {
      render(S);
      return;
    }
    acc += dt;
    var steps = 0;
    while (acc >= STEP && steps < 5) {
      S = update(S, STEP, held);
      acc -= STEP;
      steps++;
    }
    if (S.phase === "over" && overlay.style.display !== "flex") {
      showOver(S.over);
    }
    render(S);
  }

  // ---- Input: arrows/WASD, space, shift hop, P, M, Esc ------------------
  var GAME_KEYS = {
    ArrowLeft: 1, ArrowRight: 1, ArrowUp: 1, ArrowDown: 1, " ": 1,
    a: 1, d: 1, w: 1, s: 1, A: 1, D: 1, W: 1, S: 1,
    Shift: 1, p: 1, P: 1, m: 1, M: 1, Escape: 1, Enter: 1
  };
  function focused() {
    return document.activeElement === canvas;
  }
  function channelHop() {
    var nx = rand(40, S.w - 40);
    var ny = rand(40, S.h - 40);
    var occupied = S.rocks.some(function (r) {
      return dist2(r.x, r.y, nx, ny) < 70 * 70;
    });
    var ship = Object.assign({}, S.ship);
    ship.x = nx;
    ship.y = ny;
    ship.vx = 0;
    ship.vy = 0;
    ship.invuln = Math.max(ship.invuln, 1);
    var n = Object.assign({}, S);
    n.ship = ship;
    if (occupied) {
      damageRssi(n, ship, 6);
      n.banner = { text: "CHANNEL BUSY, -6 dBm", ttl: 1.4 };
    } else {
      n.banner = { text: "CHANNEL HOP", ttl: 0.9 };
    }
    S = n;
    beep(520, 0.07, "sine");
  }
  function leave() {
    if (window.htmx) {
      window.htmx.ajax("GET", "/", { target: "#content", swap: "innerHTML", pushUrl: true });
    } else {
      window.location.assign("/");
    }
  }
  function onKeyDown(e) {
    var debugJump = DEBUG && (e.key === "]" || e.key === "[");
    if (!GAME_KEYS[e.key] && !debugJump) {
      return;
    }
    if (!focused()) {
      return;
    }
    e.preventDefault();
    var k = e.key;
    if (debugJump) {
      jumpLevel(k === "]" ? 1 : -1);
      return;
    }
    if (k === "ArrowLeft" || k === "a" || k === "A") {
      held.left = true;
    } else if (k === "ArrowRight" || k === "d" || k === "D") {
      held.right = true;
    } else if (k === "ArrowUp" || k === "w" || k === "W") {
      held.thrust = true;
    } else if (k === "ArrowDown" || k === "s" || k === "S") {
      held.thrust = true;
    } else if (k === " ") {
      held.fire = true;
    } else if (k === "Shift") {
      if (!e.repeat && S.phase === "play") {
        channelHop();
      }
    } else if (k === "p" || k === "P") {
      if (!e.repeat && S.phase === "play") {
        S = Object.assign({}, S);
        S.paused = !S.paused;
      }
    } else if (k === "m" || k === "M") {
      if (!e.repeat) {
        store.mute = !store.mute;
        saveStore();
      }
    } else if (k === "Escape") {
      leave();
    } else if (k === "Enter") {
      if (S.phase === "over") {
        hideOver();
        S = initialState(S.w, S.h);
        showHelp();
      }
    }
  }
  function onKeyUp(e) {
    var k = e.key;
    if (k === "ArrowLeft" || k === "a" || k === "A") {
      held.left = false;
    } else if (k === "ArrowRight" || k === "d" || k === "D") {
      held.right = false;
    } else if (k === "ArrowUp" || k === "w" || k === "W" || k === "ArrowDown" || k === "s" || k === "S") {
      if (!heldTouch.thrust) {
        held.thrust = false;
      }
    } else if (k === " ") {
      held.fire = false;
    }
  }

  // Touch controls under 768 px or coarse pointers.
  var heldTouch = { thrust: false };
  var touchHandlers = [];
  function setupTouch() {
    var coarse = false;
    try {
      coarse = window.matchMedia("(pointer: coarse)").matches;
    } catch (e) {
      /* ignore */
    }
    if (!coarse && window.innerWidth >= 768) {
      return;
    }
    touch.hidden = false;
    var map = { left: "left", right: "right", thrust: "thrust", fire: "fire" };
    Array.prototype.forEach.call(touch.querySelectorAll("button"), function (btn) {
      var name = map[btn.getAttribute("data-ps")];
      if (!name) {
        return;
      }
      var down = function (e) {
        e.preventDefault();
        if (name === "thrust") {
          heldTouch.thrust = true;
        }
        held[name] = true;
        try {
          canvas.focus({ preventScroll: true });
        } catch (err) {
          /* ignore */
        }
      };
      var up = function (e) {
        e.preventDefault();
        if (name === "thrust") {
          heldTouch.thrust = false;
        }
        held[name] = false;
      };
      btn.addEventListener("pointerdown", down);
      btn.addEventListener("pointerup", up);
      btn.addEventListener("pointercancel", up);
      btn.addEventListener("pointerleave", up);
      touchHandlers.push([btn, "pointerdown", down], [btn, "pointerup", up],
        [btn, "pointercancel", up], [btn, "pointerleave", up]);
    });
  }
  setupTouch();

  // ---- Lifecycle and teardown -------------------------------------------
  var ro = null;
  try {
    ro = new ResizeObserver(function () {
      fitCanvas();
    });
    ro.observe(stage);
  } catch (e) {
    ro = null;
  }
  function onVis() {
    if (document.hidden) {
      if (!S.paused) {
        S = Object.assign({}, S);
        S.autoPaused = true;
      }
    } else if (S.autoPaused) {
      S = Object.assign({}, S);
      S.autoPaused = false;
    }
  }
  function onBeforeSwap(evt) {
    var target = evt.detail && evt.detail.target;
    if (target && (target.id === "content" || (target.closest && target.closest("#content")))) {
      teardown();
    }
  }
  var mo = null;
  try {
    mo = new MutationObserver(function () {
      THEME = readTheme();
      applyChrome();
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  } catch (e) {
    mo = null;
  }
  function onOverlayTap() {
    if (S.phase === "over") {
      hideOver();
      S = initialState(S.w, S.h);
      showHelp();
    }
  }

  document.addEventListener("keydown", onKeyDown);
  document.addEventListener("keyup", onKeyUp);
  document.addEventListener("visibilitychange", onVis);
  window.addEventListener("pagehide", teardown);
  document.addEventListener("htmx:beforeSwap", onBeforeSwap);
  overlay.addEventListener("click", onOverlayTap);
  document.addEventListener("keydown", startPlay);
  document.addEventListener("pointerdown", startPlay);
  document.addEventListener("touchstart", startPlay);

  function teardown() {
    cancelAnimationFrame(raf);
    raf = 0;
    document.removeEventListener("keydown", onKeyDown);
    document.removeEventListener("keyup", onKeyUp);
    document.removeEventListener("visibilitychange", onVis);
    window.removeEventListener("pagehide", teardown);
    document.removeEventListener("htmx:beforeSwap", onBeforeSwap);
    overlay.removeEventListener("click", onOverlayTap);
    document.removeEventListener("keydown", startPlay);
    document.removeEventListener("pointerdown", startPlay);
    document.removeEventListener("touchstart", startPlay);
    touchHandlers.forEach(function (h) {
      h[0].removeEventListener(h[1], h[2]);
    });
    touchHandlers = [];
    diffHandlers.forEach(function (h) {
      h[0].removeEventListener(h[1], h[2]);
    });
    diffHandlers = [];
    if (ro) {
      ro.disconnect();
      ro = null;
    }
    if (mo) {
      mo.disconnect();
      mo = null;
    }
    if (window.__packetstorm === teardown) {
      window.__packetstorm = null;
    }
  }
  window.__packetstorm = teardown;

  try {
    canvas.focus({ preventScroll: true });
  } catch (e) {
    /* ignore */
  }
  if (S.intro) {
    showHelp();
  }
  raf = requestAnimationFrame(frame);
})();
