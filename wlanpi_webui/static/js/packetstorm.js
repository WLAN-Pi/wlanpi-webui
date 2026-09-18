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
  var store = { high: 0, mute: true };
  try {
    var rawStore = window.localStorage.getItem(LS_KEY);
    if (rawStore) {
      var parsed = JSON.parse(rawStore);
      if (parsed) {
        store = { high: +parsed.high || 0, mute: parsed.mute !== false };
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
      brand: "#f45625", page: "#101417", text: "#e6eaee",
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
      out.text = get("--text") || out.text;
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

  // ---- Level spec: band and channel progression -------------------------
  var SOURCES = ["MICROWAVE", "BABY MONITOR", "CORDLESS PHONE", "BT CLUSTER"];
  var ROGUE_SSIDS = ["Free_WiFi", "xfinitywifi", "Hotel_WiFi", "Printer_Setup", "Guest_Net"];
  function levelSpec(n) {
    if (n <= 3) {
      return {
        band: "2.4 GHz", ch: [1, 6, 11][(n - 1) % 3],
        rocks: 3 + n, speed: 22 + 7 * n, zones: 3, noise: 0.15 + 0.05 * n,
        rogues: 0, dfs: false
      };
    }
    if (n <= 7) {
      return {
        band: "5 GHz", ch: [36, 44, 149, 157][(n - 4) % 4],
        rocks: 4 + n, speed: 45 + 9 * n, zones: 2, noise: 0.3 + 0.05 * n,
        rogues: 1, dfs: true
      };
    }
    return {
      band: "6 GHz", ch: [5, 21, 37, 53, 69, 85][(n - 8) % 6],
      rocks: 6 + n, speed: 70 + 8 * n, zones: 1, noise: 0.45 + 0.03 * n,
      rogues: 2, dfs: false
    };
  }
  var TIER_R = [11, 20, 34];
  var TIER_SCORE = [60, 25, 10];
  var LINK_RATES = [54, 150, 300, 433, 866, 1200, 2400];

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
      var sp = rand(spec.speed * 0.6, spec.speed);
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
    for (i = 0; i < spec.zones; i++) {
      zones.push({ x: rand(0, w), w: rand(50, 110), dir: Math.random() < 0.5 ? -1 : 1 });
    }
    return zones;
  }

  function initialState(w, h) {
    var spec = levelSpec(1);
    return {
      w: w, h: h, t: 0, uptime: 0, phase: "play",
      ship: {
        x: w / 2, y: h / 2, vx: 0, vy: 0, a: -Math.PI / 2,
        rssi: -30, retries: 3, invuln: 0, cool: 0, thrusting: false,
        respawnWait: 0
      },
      packets: [], rocks: spawnRocks(w, h, 1, spec),
      rogues: [], deauths: [],
      zones: makeZones(w, spec),
      powers: [], parts: [],
      fx: { spread: 0, mimo: 0, beam: 0, wpa3: 0, pmf: 0 },
      combo: 0, score: 0, kills: 0, sent: 0, hits: 0, gains: [],
      dfs: { active: 0, y: 0, cool: 7, hitDone: false },
      banner: { text: "LEVEL 1  " + spec.band + " / ch " + spec.ch, ttl: 2.4 },
      shieldDropT: 0,
      shake: 0, noise: spec.noise, spec: spec,
      level: 1, band: spec.band, ch: spec.ch,
      paused: false, autoPaused: false, clearTimer: 0,
      over: null
    };
  }

  function nextLevel(S) {
    var n = Object.assign({}, S);
    n.level = S.level + 1;
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
      n.rogues.push({ x: p.x, y: p.y, vx: 0, vy: 0, cool: rand(1, 3), ssid: pick(ROGUE_SSIDS) });
    }
    n.deauths = [];
    n.dfs = { active: 0, y: 0, cool: 6, hitDone: false };
    n.banner = { text: "LEVEL " + n.level + "  " + n.band + " / ch " + n.ch, ttl: 2.4 };
    n.shieldDropT = 0;
    n.phase = "play";
    n.clearTimer = 0;
    return n;
  }

  // ---- Input ------------------------------------------------------------
  var held = { left: false, right: false, thrust: false, fire: false };

  // ---- update: pure, returns a new state --------------------------------
  function update(S, dt, input) {
    if (S.phase === "over" || S.paused) {
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
      mimo: Math.max(0, S.fx.mimo - dt),
      beam: Math.max(0, S.fx.beam - dt),
      wpa3: Math.max(0, S.fx.wpa3 - dt),
      pmf: Math.max(0, S.fx.pmf - dt)
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
      ship.cool = 0.22;
      var angles = fx.spread >= 10 ? [-0.24, -0.12, 0, 0.12, 0.24] : fx.spread > 0 ? [-0.12, 0, 0.12] : [0];
      // MU-MIMO: two spatial streams, offset to the sides and angled apart
      // so they diverge toward separate clients instead of firing in parallel.
      var emitters = fx.mimo > 0
        ? [{ off: -14, da: -0.32 }, { off: 14, da: 0.32 }]
        : [{ off: 0, da: 0 }];
      var px = Math.cos(ship.a);
      var py = Math.sin(ship.a);
      emitters.forEach(function (em) {
        var ox = ship.x + -py * em.off;
        var oy = ship.y + px * em.off;
        var base = ship.a + em.da;
        angles.forEach(function (da) {
          var sp = 460 * (inZone(ox) ? 0.55 : 1);
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
        ng.cool = Math.max(1.2, 2.8 - S.level * 0.12);
        var da = Math.atan2(ship.y - ng.y, ship.x - ng.x);
        deauths.push({ x: ng.x, y: ng.y, vx: Math.cos(da) * 230, vy: Math.sin(da) * 230, life: 4 });
        beep(220, 0.12, "sawtooth");
      }
      return ng;
    });
    var keptDeauth = [];
    deauths.forEach(function (d) {
      d.life -= dt;
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
        n.banner = { text: "DFS RADAR, CLEAR THE BAND", ttl: 1.6 };
        beep(440, 0.2, "sawtooth");
      }
      if (dfs.active > 0) {
        dfs.active -= dt;
        var front = (1 - Math.max(0, dfs.active) / DFS_DUR) * n.w;
        var inBand = Math.abs(ship.y - dfs.y) < 34;
        if (inBand && ship.x <= front && ship.respawnWait <= 0) {
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
      // Destroyed interference drops power-ups. 80 MHz bonding does not
      // exist on 2.4 GHz, so it only drops on 5 GHz and up.
      if (Math.random() < 0.18) {
        var pa = rand(0, TAU);
        var drops = ["40", "MU", "BF", "W3", "BS", "PMF"];
        if (n.band !== "2.4 GHz") {
          drops.push("80");
        }
        n.powers.push({
          x: rock.x, y: rock.y,
          vx: Math.cos(pa) * 24, vy: Math.sin(pa) * 24,
          kind: pick(drops), ttl: 9
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
      ship.rssi -= decay * dt;
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

  var POWER_NAMES = { "40": "40MHz", "80": "80MHz", "MU": "MU-MIMO", "BF": "Beamforming", "W3": "WPA3", "BS": "Band steering", "PMF": "PMF booster" };
  function applyPowerup(n, kind) {
    if (kind === "40") {
      n.fx.spread = Math.max(n.fx.spread, 8);
    } else if (kind === "80") {
      n.fx.spread = 12;
    } else if (kind === "MU") {
      n.fx.mimo = Math.max(n.fx.mimo, 10);
    } else if (kind === "BF") {
      n.fx.beam = Math.max(n.fx.beam, 10);
    } else if (kind === "W3") {
      n.fx.wpa3 = Math.max(n.fx.wpa3, 10);
    } else if (kind === "PMF") {
      n.fx.pmf = Math.max(n.fx.pmf, 10);
    } else if (kind === "BS") {
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
  var hudTimer = 0;
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
      ctx.fillText("CONGESTED", z.x, S.h / 2);
    });

    // DFS sweep band. The swept side is live; the unswept side is still safe.
    if (S.dfs.active > 0) {
      var dfsProg = 1 - Math.max(0, S.dfs.active) / DFS_DUR;
      var dfsFront = dfsProg * S.w;
      ctx.fillStyle = "rgba(211, 47, 47, 0.16)";
      ctx.fillRect(0, S.dfs.y - 34, dfsFront, 68);
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
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText("RADAR", 4, S.dfs.y - 42);
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

    // Packets with short trails.
    S.packets.forEach(function (p) {
      ctx.strokeStyle = p.ghost ? THEME.info : THEME.brand;
      ctx.lineWidth = p.ghost ? 1 : 2;
      ctx.beginPath();
      ctx.moveTo(p.x - p.vx * 0.03, p.y - p.vy * 0.03);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      ctx.fillStyle = p.ghost ? THEME.info : THEME.brand;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 2.4, 0, TAU);
      ctx.fill();
    });

    // Interference sources: seeded polygons with labels.
    S.rocks.forEach(function (r) {
      var R = TIER_R[r.tier];
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
      ctx.fillStyle = THEME.text;
      ctx.globalAlpha = 0.75;
      ctx.font = "8px " + THEME.mono;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(r.name, r.x, r.y);
      ctx.globalAlpha = 1;
    });

    // Rogue APs with fake SSID labels, and their deauth frames.
    S.rogues.forEach(function (g) {
      ctx.strokeStyle = THEME.danger;
      ctx.lineWidth = 1.6;
      var i;
      for (i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.arc(g.x, g.y, 6 + i * 6, -Math.PI * 0.8, -Math.PI * 0.2);
        ctx.stroke();
      }
      ctx.fillStyle = THEME.danger;
      ctx.beginPath();
      ctx.arc(g.x, g.y, 2.5, 0, TAU);
      ctx.fill();
      ctx.font = "9px " + THEME.mono;
      ctx.textAlign = "center";
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
      ctx.fillStyle = "rgba(0, 0, 0, 0.68)";
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
      ctx.fillText("link quality bonus +" + (S.clearBonus || 0) + " Mbps", S.w / 2, py0 + 68);
      var nextSpec = levelSpec(S.level + 1);
      ctx.fillText("next: " + nextSpec.band + " / ch " + nextSpec.ch, S.w / 2, py0 + 98);
      var clearProg = 1 - Math.max(0, S.clearTimer) / CLEAR_DUR;
      ctx.fillStyle = "rgba(255, 255, 255, 0.18)";
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
    if (S.t < hudTimer) {
      hudTimer = 0;
    }
    if (S.t - hudTimer > 0.1) {
      hudTimer = S.t;
      var link = LINK_RATES[Math.min(S.combo, LINK_RATES.length - 1)];
      var fxBits = [];
      if (S.fx.spread > 0) {
        fxBits.push((S.fx.spread >= 10 ? "80MHz" : "40MHz") + " " + Math.ceil(S.fx.spread) + "s");
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
        fxBits.push("PMF " + Math.ceil(S.fx.pmf) + "s");
      }
      setHud("ps-score", Math.round(S.score) + " Mbps");
      setHud("ps-rssi", Math.round(S.ship.rssi) + " dBm");
      setHud("ps-retries", "retries " + Math.max(0, S.ship.retries));
      setHud("ps-level", "level " + S.level);
      setHud("ps-band", S.band + " / ch " + S.ch);
      setHud("ps-link", "link " + link + "M");
      setHud("ps-fx", fxBits.join("  "));
      setHud("ps-high", "best " + store.high + " Mbps");
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
    '<span id="ps-high"></span>';
  hud.setAttribute("style",
    "position:absolute;top:8px;left:10px;right:10px;display:flex;flex-wrap:wrap;" +
    "gap:4px 14px;font-family:" + THEME.mono + ";font-size:12px;color:" + THEME.text + ";" +
    "pointer-events:none;text-shadow:0 1px 2px rgba(0,0,0,0.6);");

  var overlay = document.createElement("div");
  overlay.id = "packetstorm-over";
  overlay.setAttribute("style", "display:none;position:absolute;inset:0;align-items:center;" +
    "justify-content:center;background:rgba(0,0,0,0.55);");
  overlay.innerHTML = '<div id="ps-overbox" style="font-family:' + THEME.mono +
    ';color:' + THEME.text + ';text-align:center;line-height:1.7;"></div>';
  stage.appendChild(overlay);

  function showOver(o) {
    var box = document.getElementById("ps-overbox");
    if (!box) {
      return;
    }
    box.innerHTML =
      "SPEED TEST RESULT<br>" +
      "peak " + o.peak.toFixed(1) + " Mbps<br>" +
      "average " + o.avg.toFixed(1) + " Mbps<br>" +
      "packets sent " + o.sent + "<br>" +
      "packet loss " + o.loss.toFixed(1) + "%<br>" +
      "uptime " + Math.round(o.uptime) + "s<br>" +
      "reached " + S.band + " / ch " + S.ch + ", level " + o.level + "<br>" +
      "<br>ENTER OR TAP TO RETEST";
    overlay.style.display = "flex";
  }
  function hideOver() {
    overlay.style.display = "none";
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
    if (!GAME_KEYS[e.key]) {
      return;
    }
    if (!focused()) {
      return;
    }
    e.preventDefault();
    var k = e.key;
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
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  } catch (e) {
    mo = null;
  }
  function onOverlayTap() {
    if (S.phase === "over") {
      hideOver();
      S = initialState(S.w, S.h);
    }
  }

  document.addEventListener("keydown", onKeyDown);
  document.addEventListener("keyup", onKeyUp);
  document.addEventListener("visibilitychange", onVis);
  window.addEventListener("pagehide", teardown);
  document.addEventListener("htmx:beforeSwap", onBeforeSwap);
  overlay.addEventListener("click", onOverlayTap);

  function teardown() {
    cancelAnimationFrame(raf);
    raf = 0;
    document.removeEventListener("keydown", onKeyDown);
    document.removeEventListener("keyup", onKeyUp);
    document.removeEventListener("visibilitychange", onVis);
    window.removeEventListener("pagehide", teardown);
    document.removeEventListener("htmx:beforeSwap", onBeforeSwap);
    overlay.removeEventListener("click", onOverlayTap);
    touchHandlers.forEach(function (h) {
      h[0].removeEventListener(h[1], h[2]);
    });
    touchHandlers = [];
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
  raf = requestAnimationFrame(frame);
})();
