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

  /* Split headline words for a staggered rise */
  document.querySelectorAll("[data-split]").forEach(function (el) {
    if (reduce) return;
    var words = el.textContent.trim().split(/\s+/);
    el.setAttribute("aria-label", el.textContent.trim());
    el.innerHTML = words.map(function (w, i) {
      return '<span class="split-word" aria-hidden="true"><span style="--w:' + i + '">' + w.replace(/</g, "&lt;") + "</span></span>";
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

  /* Public header: solid after scrolling, hides while scrolling down */
  var header = document.querySelector("[data-header]");
  if (header) {
    var lastY = window.scrollY;
    var onScroll = function () {
      var y = window.scrollY;
      header.classList.toggle("is-scrolled", y > 40);
      header.classList.toggle("is-hidden", y > 300 && y > lastY && !root.classList.contains("nav-open"));
      lastY = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

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

  /* Demo login chips fill the form (local DEBUG only) */
  document.querySelectorAll("[data-demo-user]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var u = document.getElementById("id_username"), p = document.getElementById("id_password");
      if (u) u.value = chip.getAttribute("data-demo-user");
      if (p) { p.value = chip.getAttribute("data-demo-pass") || ""; p.focus(); }
    });
  });
})();
