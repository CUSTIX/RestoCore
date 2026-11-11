/* Home page, "The ritual": the scene stays pinned while the steps scroll past; the kettle pours and
   the cup fills with scroll progress, and the step in view lights up.
   The scene is decorative (aria-hidden); the steps read the same without this script. */
(function () {
  "use strict";
  var widget = document.querySelector("[data-pour]");
  var zone = document.querySelector("[data-pour-zone]");
  if (!widget || !zone) return;
  var kettle = widget.querySelector("[data-pour-kettle]");
  var stream = widget.querySelector("[data-pour-stream]");
  var liquid = widget.querySelector("[data-pour-liquid]");
  var crema = widget.querySelector("[data-pour-crema]");
  var label = widget.querySelector("[data-pour-label]");
  var steps = zone.querySelectorAll("[data-pour-step]");
  zone.classList.add("is-live"); /* only dim inactive steps once the script runs */

  var SPOUT_Y = 55, CUP_BOTTOM = 194, CUP_DEPTH = 44, MAX_TILT = 40;
  function clamp(n) { return Math.max(0, Math.min(1, n)); }
  function ease(t) { return t * t * (3 - 2 * t); }

  var last = -1, ticking = false;
  function render() {
    ticking = false;
    var r = zone.getBoundingClientRect(), vh = window.innerHeight;
    /* 0 when the first step's top reaches 60% of the screen, 1 when the last step's bottom does. */
    var p = clamp((vh * 0.6 - r.top) / Math.max(1, r.height));
    if (Math.abs(p - last) < 0.0005) return;
    last = p;
    var active = Math.min(steps.length - 1, Math.floor(p * steps.length));
    steps.forEach(function (s, i) { s.classList.toggle("is-active", i === active); });

    /* Tilt in over the first 10%, hold while pouring, tilt back over the last stretch. */
    var tilt = p < 0.1 ? MAX_TILT * ease(p / 0.1)
      : p < 0.88 ? MAX_TILT : MAX_TILT * (1 - ease(clamp((p - 0.88) / 0.08)));
    var fill = clamp((p - 0.1) / 0.78);
    var surface = CUP_BOTTOM - fill * CUP_DEPTH;
    var flow = clamp((tilt - 28) / 10);

    kettle.setAttribute("transform", "rotate(" + tilt.toFixed(2) + " 68 54)");
    stream.setAttribute("height", Math.max(0, (surface - SPOUT_Y) * flow).toFixed(1));
    stream.style.opacity = flow;
    liquid.setAttribute("y", surface.toFixed(1));
    crema.setAttribute("y", (surface - 1).toFixed(1));
    crema.style.opacity = fill > 0.02 ? 1 : 0;
    widget.classList.toggle("is-flowing", flow > 0.05);
    widget.classList.toggle("is-ready", fill >= 1 && tilt < 1);
    label.textContent = p < 0.02 ? "Scroll to brew" : fill < 1 ? "Brewing " + Math.round(fill * 100) + "%" : "Ready to sip";
  }
  function request() { if (!ticking) { ticking = true; requestAnimationFrame(render); } }
  window.addEventListener("scroll", request, { passive: true });
  window.addEventListener("resize", function () { last = -1; request(); });
  render();
})();
