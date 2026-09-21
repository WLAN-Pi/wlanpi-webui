/* Beacon stage: loads the vendored Emscripten engine, fetches the game data
   into the Emscripten filesystem, drives it from on-screen controls on touch
   devices, and tears the whole runtime down on htmx swaps.

   The engine is a classic script that reads the global `Module` at load time,
   so we configure it, then append the script. Everything lives only while
   /beacon is mounted; nothing here runs on any other page. */
(function () {
  "use strict";

  var stage = document.getElementById("beacon-stage");
  if (!stage) {
    return;
  }
  var canvas = document.getElementById("beacon-canvas");
  var loading = document.getElementById("beacon-loading");
  var loadingText = document.getElementById("beacon-loading-text");
  var retryEl = document.getElementById("beacon-retry");
  var touchEl = document.getElementById("beacon-touch");
  var dpad = document.getElementById("beacon-dpad");
  var rotateEl = document.getElementById("beacon-rotate");
  var ENGINE = "/static/vendor/beacon/";
  var DATA_URL = "/beacon/data";
  var DATA_TIMEOUT = 120000;
  var moduleRef = null;
  var resizeHandler = null;
  var started = false;
  var gameStarted = false;
  var touchHandlers = [];
  var retryHandler = null;
  var firstInteractionHandler = null;
  var dataLoading = false;

  var IS_TOUCH = false;
  try {
    IS_TOUCH =
      window.matchMedia("(pointer: coarse)").matches || window.innerWidth < 768;
  } catch (e) {
    IS_TOUCH = window.innerWidth < 768;
  }

  // SDL maps keyboard input from the DOM event's keyCode/which/key/code. These
  // mirror Chocolate Doom's default bindings.
  var KEYS = {
    up: { key: "ArrowUp", code: "ArrowUp", keyCode: 38 },
    down: { key: "ArrowDown", code: "ArrowDown", keyCode: 40 },
    left: { key: "ArrowLeft", code: "ArrowLeft", keyCode: 37 },
    right: { key: "ArrowRight", code: "ArrowRight", keyCode: 39 },
    fire: { key: "v", code: "KeyV", keyCode: 86 },
    // Use opens doors in-game (Space) and confirms menus (Enter). Enter is
    // unbound in-game, so sending both is safe and removes the old OK button.
    use: [
      { key: " ", code: "Space", keyCode: 32 },
      { key: "Enter", code: "Enter", keyCode: 13 },
    ],
    run: { key: "Shift", code: "ShiftLeft", keyCode: 16 },
    // Opens/closes the Doom menu and backs out of submenus.
    menu: { key: "Escape", code: "Escape", keyCode: 27 },
  };

  function setStatus(text) {
    if (loadingText) {
      loadingText.textContent = text;
    }
  }

  // The game is 4:3 (Chocolate Doom's aspect_ratio_correct default); letterbox
  // it inside the stage rather than stretching.
  var RATIO = 4 / 3;
  var MIN_W = 320;
  var MIN_H = 240;
  var MAX_W = 2048;
  var MAX_H = 1536;
  // Window size in CSS px that makes SDL's high-DPI drawable (window * dpr)
  // equal the canvas buffer. Set by bufferSize() before the engine loads.
  var winSize = { w: 0, h: 0 };

  function fitBox() {
    if (!canvas || !stage) {
      return null;
    }
    var aw = stage.clientWidth - 8;
    var ah = stage.clientHeight - 8;
    if (aw <= 0 || ah <= 0) {
      return null;
    }
    var w = aw;
    var h = aw / RATIO;
    if (h > ah) {
      h = ah;
      w = ah * RATIO;
    }
    return { w: w, h: h };
  }

  function fit() {
    var box = fitBox();
    if (!box) {
      return;
    }
    canvas.style.width = Math.floor(box.w) + "px";
    canvas.style.height = Math.floor(box.h) + "px";
  }

  function even(n) {
    return Math.max(2, Math.round(n / 2) * 2);
  }

  // The engine never sizes its own drawing buffer (it stays at the HTML
  // default 300x150 unless fullscreen), so a 320x240 game gets stretched by the
  // browser. Size it ourselves to the display's device resolution, clamped.
  // SDL is built with high-DPI, so its renderer drawable is window * dpr; the
  // window we hand it must therefore be buffer / dpr or the game renders
  // zoomed and clipped (e.g. only the bottom-left quadrant on Retina).
  function bufferSize() {
    var box = fitBox();
    if (!box) {
      return;
    }
    var dpr = window.devicePixelRatio || 1;
    var w = Math.round(box.w * dpr);
    var h = Math.round(box.h * dpr);
    w = Math.min(MAX_W, Math.max(MIN_W, w));
    h = Math.min(MAX_H, Math.max(MIN_H, h));
    if (w / h > RATIO) {
      w = Math.round(h * RATIO);
    } else if (w / h < RATIO) {
      h = Math.round(w / RATIO);
    }
    canvas.width = even(w);
    canvas.height = even(h);
    winSize.w = Math.round(canvas.width / dpr);
    winSize.h = Math.round(canvas.height / dpr);
  }

  // Synthesise a keyboard event. A plain Event (not KeyboardEvent) is used
  // because KeyboardEvent's keyCode/which are read-only and SDL ignores them.
  // Dispatch once on window: SDL's handler lives there, and dispatching on
  // document/canvas too would bubble back to window and fire it repeatedly
  // (menus would skip items).
  function pressOne(spec, down) {
    var evt = document.createEvent("Event");
    evt.initEvent(down ? "keydown" : "keyup", true, true);
    evt.keyCode = spec.keyCode;
    evt.which = spec.keyCode;
    evt.charCode = 0;
    evt.key = spec.key;
    evt.code = spec.code;
    evt.location = 0;
    evt.ctrlKey = false;
    evt.shiftKey = false;
    evt.altKey = false;
    evt.metaKey = false;
    evt.repeat = false;
    window.dispatchEvent(evt);
  }

  // A button may map to one key spec or several (Use sends Space + Enter).
  function press(spec, down) {
    var specs = spec instanceof Array ? spec : [spec];
    for (var i = 0; i < specs.length; i++) {
      pressOne(specs[i], down);
    }
  }

  function resumeAudio() {
    try {
      var sdl = moduleRef && moduleRef.SDL2;
      if (
        sdl &&
        sdl.audioContext &&
        sdl.audioContext.state === "suspended" &&
        sdl.audioContext.resume
      ) {
        sdl.audioContext.resume();
      }
    } catch (e) {
      /* ignore */
    }
  }

  // Stream the IWAD into the Emscripten FS with a progress readout. The run
  // dependency is only released on success, so a stalled or failed download
  // pauses the runtime (instead of starting the game without data) and the
  // retry button can try again.
  function loadData(mod) {
    if (dataLoading) {
      return;
    }
    dataLoading = true;
    if (retryEl) {
      retryEl.hidden = true;
    }
    var controller = null;
    var timer = 0;
    try {
      controller = new AbortController();
    } catch (e) {
      controller = null;
    }
    if (controller) {
      timer = setTimeout(function () {
        controller.abort();
      }, DATA_TIMEOUT);
    }
    var options = { credentials: "same-origin" };
    if (controller) {
      options.signal = controller.signal;
    }
    function clearTimer() {
      if (timer) {
        clearTimeout(timer);
        timer = 0;
      }
    }
    setStatus("Loading game data\u2026");
    fetch(DATA_URL, options)
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("data " + resp.status);
        }
        var total = parseInt(resp.headers.get("Content-Length") || "0", 10);
        if (resp.body && resp.body.getReader && total > 0) {
          var reader = resp.body.getReader();
          var chunks = [];
          var received = 0;
          var pump = function () {
            return reader.read().then(function (result) {
              if (result.done) {
                var out = new Uint8Array(received);
                var offset = 0;
                for (var i = 0; i < chunks.length; i++) {
                  out.set(chunks[i], offset);
                  offset += chunks[i].length;
                }
                return out;
              }
              chunks.push(result.value);
              received += result.value.length;
              setStatus(
                "Loading game data\u2026 " +
                  Math.min(100, Math.round((received / total) * 100)) +
                  "%"
              );
              return pump();
            });
          };
          return pump();
        }
        return resp.arrayBuffer().then(function (buf) {
          return new Uint8Array(buf);
        });
      })
      .then(function (bytes) {
        clearTimer();
        mod.FS.writeFile("data.wad", bytes);
        dataLoading = false;
        mod.removeRunDependency("data");
      })
      .catch(function () {
        clearTimer();
        dataLoading = false;
        setStatus("Could not load game data.");
        if (retryEl) {
          retryEl.hidden = false;
        }
      });
  }

  function mainArgs() {
    return [
      "-iwad",
      "data.wad",
      "-window",
      "-nogui",
      // OPL music emulation busy-loops the browser main thread and freezes the
      // whole WebUI tab. Sound effects are unaffected.
      "-nomusic",
      // SDL's high-DPI drawable is window * dpr; passing buffer / dpr makes the
      // drawable equal our canvas buffer, so the game fills it at any
      // devicePixelRatio instead of rendering zoomed.
      "-width",
      String(winSize.w),
      "-height",
      String(winSize.h),
      "-config",
      "default.cfg",
    ];
  }

  function launch() {
    try {
      canvas.focus({ preventScroll: true });
    } catch (e) {
      /* ignore */
    }
    try {
      window.callMain(mainArgs());
    } catch (e) {
      /* surfaced by the engine's own error path */
    }
    resumeAudio();
    fit();
  }

  function enterFullscreen() {
    try {
      if (stage.requestFullscreen) {
        var p = stage.requestFullscreen();
        if (p && p.catch) {
          p.catch(function () {});
        }
        return;
      }
      if (stage.webkitRequestFullscreen) {
        stage.webkitRequestFullscreen();
      }
    } catch (e) {
      /* ignore */
    }
  }

  function onFullscreenChange() {
    fit();
    updateRotate();
  }

  // Stop the browser's default handling of game keys: page scroll and, on
  // macOS, Shift+arrow text selection. The event still reaches SDL.
  var GUARD_KEYCODES = { 37: 1, 38: 1, 39: 1, 40: 1, 32: 1, 16: 1, 86: 1 };
  function onKeyGuard(e) {
    if (GUARD_KEYCODES[e.keyCode]) {
      e.preventDefault();
    }
  }

  function startGame() {
    if (gameStarted) {
      return;
    }
    gameStarted = true;
    if (loading) {
      loading.style.display = "none";
    }
    launch();
  }

  // The game auto-starts and is visible immediately. The first tap/keypress is
  // the user gesture we need for audio and (on touch) real fullscreen, so we
  // take both from it rather than gating the game behind an overlay.
  function onFirstInteraction() {
    stage.removeEventListener("pointerdown", onFirstInteraction, true);
    firstInteractionHandler = null;
    resumeAudio();
    if (IS_TOUCH) {
      enterFullscreen();
    }
  }

  function setupTouch() {
    if (!IS_TOUCH || !touchEl) {
      return;
    }
    touchEl.hidden = false;
    var buttons = touchEl.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      var btn = buttons[i];
      var spec = KEYS[btn.getAttribute("data-key")];
      if (!spec) {
        continue;
      }
      (function (button, keySpec) {
        var down = function (e) {
          e.preventDefault();
          press(keySpec, true);
        };
        var up = function (e) {
          e.preventDefault();
          press(keySpec, false);
        };
        button.addEventListener("pointerdown", down);
        button.addEventListener("pointerup", up);
        button.addEventListener("pointercancel", up);
        button.addEventListener("pointerleave", up);
        touchHandlers.push(
          [button, "pointerdown", down],
          [button, "pointerup", up],
          [button, "pointercancel", up],
          [button, "pointerleave", up]
        );
      })(btn, spec);
    }
  }

  // One touch surface, eight-way: derive the directions from where the thumb
  // points, so a diagonal (forward + turn) holds both keys at once.
  function setupDpad() {
    if (!IS_TOUCH || !dpad) {
      return;
    }
    var active = { up: false, down: false, left: false, right: false };
    var pressing = false;

    function setDir(dir, on) {
      if (active[dir] === on) {
        return;
      }
      active[dir] = on;
      press(KEYS[dir], on);
      var el = dpad.querySelector('[data-dir="' + dir + '"]');
      if (el) {
        el.classList.toggle("is-active", on);
      }
    }

    function releaseAll() {
      pressing = false;
      setDir("up", false);
      setDir("down", false);
      setDir("left", false);
      setDir("right", false);
    }

    function update(x, y) {
      var r = dpad.getBoundingClientRect();
      var dx = x - (r.left + r.width / 2);
      var dy = y - (r.top + r.height / 2);
      var ax = Math.abs(dx);
      var ay = Math.abs(dy);
      if (ax < r.width * 0.12 && ay < r.height * 0.12) {
        setDir("up", false);
        setDir("down", false);
        setDir("left", false);
        setDir("right", false);
        return;
      }
      // 0.414 = tan(22.5deg): each axis is active within 67.5deg, giving
      // clean 45deg diagonals.
      var t = 0.414;
      setDir("up", dy < 0 && ay >= ax * t);
      setDir("down", dy > 0 && ay >= ax * t);
      setDir("left", dx < 0 && ax >= ay * t);
      setDir("right", dx > 0 && ax >= ay * t);
    }

    var down = function (e) {
      e.preventDefault();
      pressing = true;
      try {
        dpad.setPointerCapture(e.pointerId);
      } catch (err) {
        /* ignore */
      }
      update(e.clientX, e.clientY);
    };
    var move = function (e) {
      if (!pressing) {
        return;
      }
      e.preventDefault();
      update(e.clientX, e.clientY);
    };
    var up = function (e) {
      e.preventDefault();
      releaseAll();
    };

    dpad.addEventListener("pointerdown", down);
    dpad.addEventListener("pointermove", move);
    dpad.addEventListener("pointerup", up);
    dpad.addEventListener("pointercancel", up);
    touchHandlers.push(
      [dpad, "pointerdown", down],
      [dpad, "pointermove", move],
      [dpad, "pointerup", up],
      [dpad, "pointercancel", up]
    );
  }

  function updateRotate() {
    if (!rotateEl) {
      return;
    }
    rotateEl.hidden = !(IS_TOUCH && window.innerHeight > window.innerWidth);
  }

  function teardown() {
    if (moduleRef) {
      try {
        if (moduleRef.pauseMainLoop) {
          moduleRef.pauseMainLoop();
        }
      } catch (e) {
        /* ignore */
      }
      try {
        var sdl = moduleRef.SDL2;
        if (sdl && sdl.audioContext && sdl.audioContext.close) {
          sdl.audioContext.close();
        }
      } catch (e) {
        /* ignore */
      }
    }
    moduleRef = null;
    try {
      window.Module = null;
      window.callMain = null;
    } catch (e) {
      /* ignore */
    }
    var script = document.getElementById("beacon-engine");
    if (script && script.parentNode) {
      script.parentNode.removeChild(script);
    }
    if (resizeHandler) {
      window.removeEventListener("resize", resizeHandler);
      window.removeEventListener("orientationchange", resizeHandler);
      resizeHandler = null;
    }
    for (var i = 0; i < touchHandlers.length; i++) {
      touchHandlers[i][0].removeEventListener(touchHandlers[i][1], touchHandlers[i][2]);
    }
    touchHandlers = [];
    if (firstInteractionHandler) {
      stage.removeEventListener("pointerdown", firstInteractionHandler, true);
      firstInteractionHandler = null;
    }
    if (retryEl && retryHandler) {
      retryEl.removeEventListener("click", retryHandler);
      retryHandler = null;
    }
    stage.removeEventListener("keydown", onKeyGuard, true);
    document.removeEventListener("fullscreenchange", onFullscreenChange);
    try {
      if (document.fullscreenElement) {
        var leaving = document.exitFullscreen();
        if (leaving && leaving.catch) {
          leaving.catch(function () {});
        }
      }
    } catch (e) {
      /* ignore */
    }
    document.removeEventListener("htmx:beforeSwap", onBeforeSwap);
    window.removeEventListener("pagehide", teardown);
    if (window.__beacon === teardown) {
      window.__beacon = null;
    }
  }

  function onBeforeSwap(evt) {
    var target = evt.detail && evt.detail.target;
    if (
      target &&
      (target.id === "content" ||
        (target.closest && target.closest("#content")))
    ) {
      teardown();
    }
  }

  function boot() {
    if (started) {
      return;
    }
    started = true;
    // Size the drawing buffer before the engine builds its renderer, then set
    // the CSS box. The buffer is fixed after boot; CSS handles later resizes.
    bufferSize();
    fit();

    var mod = {
      noInitialRun: true,
      canvas: canvas,
      locateFile: function (path) {
        return ENGINE + path;
      },
      print: function () {},
      printErr: function (text) {
        if (window.console && window.console.warn) {
          window.console.warn("[beacon]", text);
        }
      },
      setStatus: function (text) {
        if (text) {
          setStatus(text);
        }
      },
      onRuntimeInitialized: function () {
        startGame();
      },
      preRun: [
        function () {
          // Keep the mouse out of the browser's pointer lock; keyboard only.
          try {
            mod.FS.writeFile(
              "default.cfg",
              // key_fire is remapped from Ctrl to 'v': Ctrl+arrow is macOS
              // Mission Control (workspace switch), which fires while turning.
              // 'f' is already fullscreen; 'v' is free. Config keys are stored
              // as Doom scancodes, so this is scantokey[47] ('v'), not 'v'.
              "use_mouse 0\ngrabmouse 0\nforce_software_renderer 0\n" +
                "key_fire 47\nscreenblocks 10\nsnd_channels 8\n" +
                "snd_musicdevice 3\nsnd_sfxdevice 3\n"
            );
          } catch (e) {
            /* ignore */
          }
        },
        function () {
          mod.addRunDependency("data");
          loadData(mod);
        },
      ],
    };

    window.Module = mod;
    moduleRef = mod;

    var script = document.createElement("script");
    script.id = "beacon-engine";
    script.src = ENGINE + "beacon.js";
    script.async = true;
    script.onerror = function () {
      setStatus("Could not load the game engine.");
    };
    document.body.appendChild(script);

    resizeHandler = function () {
      fit();
      updateRotate();
    };
    window.addEventListener("resize", resizeHandler);
    window.addEventListener("orientationchange", resizeHandler);
    stage.addEventListener("keydown", onKeyGuard, true);
    document.addEventListener("fullscreenchange", onFullscreenChange);

    firstInteractionHandler = onFirstInteraction;
    stage.addEventListener("pointerdown", onFirstInteraction, true);

    if (retryEl) {
      retryHandler = function (e) {
        e.preventDefault();
        loadData(moduleRef);
      };
      retryEl.addEventListener("click", retryHandler);
    }

    setupTouch();
    setupDpad();
    updateRotate();
    document.addEventListener("htmx:beforeSwap", onBeforeSwap);
    window.addEventListener("pagehide", teardown);
  }

  window.__beacon = teardown;
  boot();
})();
