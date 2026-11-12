/* RestoCore motion & small UI behaviours. Progressive enhancement: pages work without it. */
(function () {
  "use strict";
  var root = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };

  /* Theme toggle (light / dark) */
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store.set("rc-theme", next);
    });
  });

  /* Sidebar collapse (desktop) and drawer (mobile) */
  document.querySelectorAll("[data-sidebar-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var on = root.classList.toggle("sidebar-collapsed");
      store.set("rc-sidebar", on ? "collapsed" : "open");
    });
  });
  document.querySelectorAll("[data-nav-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var open = root.classList.toggle("nav-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") root.classList.remove("nav-open");
  });
  document.querySelectorAll(".nav-sheet a").forEach(function (a) {
    a.addEventListener("click", function () { root.classList.remove("nav-open"); });
  });

  /* Split headline words for a staggered rise */
  document.querySelectorAll("[data-split]").forEach(function (el) {
    if (reduce) return;
    var text = el.textContent.trim();
    var safe = function (s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;"); };
    /* Screen readers read one hidden copy of the sentence; the animated word spans are hidden. */
    el.innerHTML = '<span class="sr-only">' + safe(text) + "</span>" + text.split(/\s+/).map(function (w, i) {
      return '<span class="split-word" aria-hidden="true"><span style="--w:' + i + '">' + safe(w) + "</span></span>";
    }).join(" ");
  });

  /* Reveal on scroll (with per-parent stagger) */
  document.querySelectorAll("[data-stagger]").forEach(function (parent) {
    Array.prototype.forEach.call(parent.children, function (child, i) {
      if (child.hasAttribute("data-reveal")) child.style.setProperty("--i", i % 8);
    });
  });
  var revealables = document.querySelectorAll("[data-reveal]");
  if (reduce || !("IntersectionObserver" in window)) {
    revealables.forEach(function (el) { el.classList.add("is-visible"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add("is-visible"); io.unobserve(entry.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    revealables.forEach(function (el) { io.observe(el); });
  }

  /* Count-up numbers: <span data-count="1234.50" data-decimals="2">1,234.50</span> */
  function formatNumber(n, decimals) {
    return n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }
  function countUp(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    if (isNaN(target) || reduce) return;
    var start = null, duration = 1200;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 4);
      el.textContent = formatNumber(target * eased, decimals);
      if (p < 1) requestAnimationFrame(step); else el.textContent = formatNumber(target, decimals);
    }
    requestAnimationFrame(step);
  }
  var counters = document.querySelectorAll("[data-count]");
  if ("IntersectionObserver" in window) {
    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { countUp(e.target); co.unobserve(e.target); } });
    }, { threshold: 0.4 });
    counters.forEach(function (el) { co.observe(el); });
  }

  /* Toasts: auto-dismiss after 6s, or on close */
  function dismiss(toast) {
    if (!toast || toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    setTimeout(function () { toast.remove(); }, 380);
  }
  document.querySelectorAll(".toast").forEach(function (toast) {
    var timer = setTimeout(function () { dismiss(toast); }, 6000);
    toast.addEventListener("mouseenter", function () {
      clearTimeout(timer);
      var bar = toast.querySelector(".toast__timer");
      if (bar) bar.style.animationPlayState = "paused";
    });
    var close = toast.querySelector(".toast__close");
    if (close) close.addEventListener("click", function () { dismiss(toast); });
  });

  /* Public header: narrows and turns solid after scrolling; a thin line shows how far down the page you are */
  var header = document.querySelector("[data-header]");
  if (header) {
    var headerTick = false;
    var onScroll = function () {
      headerTick = false;
      var y = window.scrollY;
      var max = document.documentElement.scrollHeight - window.innerHeight;
      header.classList.toggle("is-scrolled", y > 40);
      header.style.setProperty("--progress", max > 0 ? Math.min(1, y / max).toFixed(4) : "0");
    };
    window.addEventListener("scroll", function () {
      if (!headerTick) { headerTick = true; requestAnimationFrame(onScroll); }
    }, { passive: true });
    window.addEventListener("resize", onScroll);
    onScroll();
  }
  /* Public mobile menu: tapping outside the sheet closes it */
  document.addEventListener("click", function (e) {
    if (!root.classList.contains("nav-open") || !document.body.classList.contains("public")) return;
    if (!e.target.closest(".nav-sheet, [data-nav-toggle]")) {
      root.classList.remove("nav-open");
      document.querySelectorAll("[data-nav-toggle]").forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
    }
  });

  /* Parallax: data-parallax="0.15" moves the element with scroll */
  var parallax = document.querySelectorAll("[data-parallax]");
  if (parallax.length && !reduce) {
    var ticking = false;
    var update = function () {
      parallax.forEach(function (el) {
        var speed = parseFloat(el.getAttribute("data-parallax")) || 0.15;
        var rect = el.parentElement.getBoundingClientRect();
        var limit = rect.height * 0.07; /* stay inside the 1.2x scale overscan: no gaps */
        var offset = (rect.top + rect.height / 2 - window.innerHeight / 2) * -speed;
        offset = Math.max(-limit, Math.min(limit, offset));
        el.style.transform = "translate3d(0," + offset.toFixed(1) + "px,0) scale(1.2)";
      });
      ticking = false;
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { requestAnimationFrame(update); ticking = true; }
    }, { passive: true });
    update();
  }

  /* 3D tilt on hover (fine pointers only) */
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (fine && !reduce) {
    document.querySelectorAll("[data-tilt]").forEach(function (card) {
      card.addEventListener("mousemove", function (e) {
        var r = card.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = "perspective(900px) rotateX(" + (-y * 6).toFixed(2) + "deg) rotateY(" + (x * 8).toFixed(2) + "deg) translateY(-4px)";
        card.style.setProperty("--mx", (x + 0.5) * 100 + "%");
        card.style.setProperty("--my", (y + 0.5) * 100 + "%");
      });
      card.addEventListener("mouseleave", function () { card.style.transform = ""; });
    });
    document.querySelectorAll("[data-magnetic]").forEach(function (btn) {
      btn.addEventListener("mousemove", function (e) {
        var r = btn.getBoundingClientRect();
        var x = e.clientX - r.left - r.width / 2, y = e.clientY - r.top - r.height / 2;
        btn.style.transform = "translate(" + (x * 0.18).toFixed(1) + "px," + (y * 0.25).toFixed(1) + "px)";
      });
      btn.addEventListener("mouseleave", function () { btn.style.transform = ""; });
    });
  }

  /* Live "elapsed" timers: <span data-since="ISO" data-late-after="15"> */
  var timers = document.querySelectorAll("[data-since]");
  function tick() {
    var now = Date.now();
    timers.forEach(function (el) {
      var mins = Math.max(0, Math.floor((now - Date.parse(el.getAttribute("data-since"))) / 60000));
      var h = Math.floor(mins / 60);
      el.textContent = h ? h + "h " + (mins % 60) + "m" : mins + "m";
      var late = parseInt(el.getAttribute("data-late-after") || "0", 10);
      if (late) el.classList.toggle("is-late", mins >= late);
    });
  }
  if (timers.length) { tick(); setInterval(tick, 30000); }

  /* Scrollspy for in-page chip navs: <nav data-spy> <a href="#section"> */
  document.querySelectorAll("[data-spy]").forEach(function (nav) {
    var links = nav.querySelectorAll('a[href^="#"]');
    if (!("IntersectionObserver" in window) || !links.length) return;
    var map = {};
    links.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a; });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.remove("is-active"); });
        var a = map[e.target.id];
        if (a) { a.classList.add("is-active"); a.scrollIntoView({ block: "nearest", inline: "center", behavior: reduce ? "auto" : "smooth" }); }
      });
    }, { rootMargin: "-35% 0px -60% 0px" });
    Object.keys(map).forEach(function (id) { var s = document.getElementById(id); if (s) spy.observe(s); });
  });

  /* Carousels: arrow buttons + drag to scroll */
  document.querySelectorAll("[data-carousel]").forEach(function (track) {
    var id = track.id;
    function step(dir) {
      var card = track.firstElementChild;
      var amount = card ? card.getBoundingClientRect().width + 20 : track.clientWidth * 0.8;
      track.scrollBy({ left: dir * amount, behavior: reduce ? "auto" : "smooth" });
    }
    document.querySelectorAll('[data-carousel-prev="' + id + '"]').forEach(function (b) { b.addEventListener("click", function () { step(-1); }); });
    document.querySelectorAll('[data-carousel-next="' + id + '"]').forEach(function (b) { b.addEventListener("click", function () { step(1); }); });
    var down = false, startX = 0, startLeft = 0, moved = false;
    track.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "mouse") return;
      down = true; moved = false; startX = e.clientX; startLeft = track.scrollLeft;
    });
    window.addEventListener("pointermove", function (e) {
      if (!down) return;
      var dx = e.clientX - startX;
      if (Math.abs(dx) > 4) { moved = true; track.classList.add("is-dragging"); }
      track.scrollLeft = startLeft - dx;
    });
    window.addEventListener("pointerup", function () { down = false; track.classList.remove("is-dragging"); });
    track.addEventListener("click", function (e) { if (moved) { e.preventDefault(); e.stopPropagation(); } }, true);
  });

  /* Pill nav: an indicator glides to the hovered link and rests on the current page */
  document.querySelectorAll("[data-nav-links]").forEach(function (nav) {
    var pill = nav.querySelector(".nav-indicator");
    if (!pill) return;
    var links = nav.querySelectorAll("a");
    var current = nav.querySelector('a[aria-current="page"]');
    function moveTo(a) {
      if (!a) { pill.style.opacity = "0"; return; }
      pill.style.width = a.offsetWidth + "px";
      pill.style.transform = "translateX(" + a.offsetLeft + "px)";
      pill.style.opacity = "1";
    }
    links.forEach(function (a) { a.addEventListener("mouseenter", function () { moveTo(a); }); a.addEventListener("focus", function () { moveTo(a); }); });
    nav.addEventListener("mouseleave", function () { moveTo(current); });
    window.addEventListener("resize", function () { moveTo(current); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { moveTo(current); });
    moveTo(current);

    /* On the home page the highlight moves to "Visit" while that section is on screen. */
    var home = current;
    nav.querySelectorAll("[data-spy-target]").forEach(function (a) {
      var section = document.getElementById(a.getAttribute("data-spy-target"));
      if (!section || !("IntersectionObserver" in window)) return;
      new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          current = e.isIntersecting ? a : home;
          if (current) current.setAttribute("aria-current", "page");
          if (e.isIntersecting && home) home.removeAttribute("aria-current");
          if (!e.isIntersecting) a.removeAttribute("aria-current");
          moveTo(current);
        });
      }, { rootMargin: "-40% 0px -40% 0px" }).observe(section);
    });
  });

  /* Photo stack: shuffles on its own; click/tap a photo, swipe, or use the arrows and dots to flip
     through. Any manual change pauses the autoplay for a few seconds. */
  document.querySelectorAll("[data-stack]").forEach(function (stack) {
    var cards = Array.prototype.slice.call(stack.querySelectorAll(".stack__card"));
    var n = cards.length;
    if (n < 2) return;
    var dots = stack.querySelectorAll("[data-stack-dot]");
    var hovering = false, holdUntil = 0;
    function front() {
      for (var i = 0; i < n; i++) if (cards[i].getAttribute("data-pos") === "0") return i;
      return 0;
    }
    function show(index) {
      cards.forEach(function (card, i) { card.setAttribute("data-pos", String((i - index + n) % n)); });
      dots.forEach(function (d, i) { d.setAttribute("aria-current", i === index ? "true" : "false"); });
    }
    function step(dir, manual) {
      show((front() + dir + n) % n);
      if (manual) holdUntil = Date.now() + 8000;
    }
    show(front());
    stack.querySelectorAll("[data-stack-next]").forEach(function (b) { b.addEventListener("click", function () { step(1, true); }); });
    stack.querySelectorAll("[data-stack-prev]").forEach(function (b) { b.addEventListener("click", function () { step(-1, true); }); });
    dots.forEach(function (d, i) { d.addEventListener("click", function () { show(i); holdUntil = Date.now() + 8000; }); });
    /* Tap/click a photo for the next one; swipe sideways to go either way. */
    var startX = null, swiped = false;
    cards.forEach(function (card) {
      card.addEventListener("pointerdown", function (e) { startX = e.clientX; swiped = false; });
      card.addEventListener("pointerup", function (e) {
        if (startX === null) return;
        var dx = e.clientX - startX;
        startX = null;
        if (Math.abs(dx) > 40) { swiped = true; step(dx < 0 ? 1 : -1, true); }
      });
      card.addEventListener("click", function () { if (!swiped) step(1, true); });
    });
    if (reduce) return;
    stack.addEventListener("mouseenter", function () { hovering = true; });
    stack.addEventListener("mouseleave", function () { hovering = false; });
    setInterval(function () {
      if (hovering || document.hidden || Date.now() < holdUntil) return;
      step(1, false);
    }, 3800);
  });

  /* Dish index: a photo follows the cursor while hovering a row (fine pointers only) */
  var preview = document.querySelector("[data-cursor-preview]");
  /* Turn on at the first real mouse movement: proves there's a mouse, unlike media queries. */
  if (preview && !reduce) window.addEventListener("mousemove", setupPreview, { once: true, passive: true });
  function setupPreview(first) {
    var rows = document.querySelectorAll("[data-dish-index] [data-preview]");
    var imgs = {};
    rows.forEach(function (row) {
      var src = row.getAttribute("data-preview");
      if (!imgs[src]) {
        var img = document.createElement("img");
        img.src = src; img.alt = ""; img.loading = "lazy";
        preview.appendChild(img);
        imgs[src] = img;
      }
      row.addEventListener("mouseenter", function () {
        Object.keys(imgs).forEach(function (k) { imgs[k].classList.toggle("is-active", k === src); });
        preview.classList.add("is-on");
      });
      row.addEventListener("mouseleave", function () { preview.classList.remove("is-on"); });
    });
    var tx = first.clientX + 170, ty = first.clientY, px = tx, py = ty;
    window.addEventListener("mousemove", function (e) { tx = e.clientX + 170; ty = e.clientY; }, { passive: true });
    (function follow() {
      px += (tx - px) * 0.14; py += (ty - py) * 0.14;
      preview.style.left = px + "px"; preview.style.top = py + "px";
      requestAnimationFrame(follow);
    })();
  }

  /* Responsive tables: copy each column heading onto its cells so phones can show rows as cards. */
  document.querySelectorAll(".table-wrap table").forEach(function (table) {
    var heads = Array.prototype.map.call(table.querySelectorAll("thead th"), function (th) { return th.textContent.trim(); });
    if (!heads.length) return;
    table.querySelectorAll("tbody tr").forEach(function (tr) {
      Array.prototype.forEach.call(tr.children, function (td, i) {
        if (heads[i]) td.setAttribute("data-label", heads[i]);
      });
    });
    table.classList.add("is-stackable");
  });

  /* Small behaviours declared in HTML, so templates need no inline JavaScript (strict CSP):
     <button data-print>, <form data-confirm="Are you sure?">, <span data-auto-reload="30"> */
  document.querySelectorAll("[data-print]").forEach(function (btn) {
    btn.addEventListener("click", function () { window.print(); });
  });
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-confirm"))) e.preventDefault();
    });
  });
  document.querySelectorAll("[data-auto-reload]").forEach(function (el) {
    var seconds = parseInt(el.getAttribute("data-auto-reload"), 10);
    if (seconds > 0) setTimeout(function () { window.location.reload(); }, seconds * 1000);
  });

  /* Demo login chips fill the form (local DEBUG only) */
  document.querySelectorAll("[data-demo-user]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var u = document.getElementById("id_username"), p = document.getElementById("id_password");
      if (u) u.value = chip.getAttribute("data-demo-user");
      if (p) { p.value = chip.getAttribute("data-demo-pass") || ""; p.focus(); }
    });
  });
})();
