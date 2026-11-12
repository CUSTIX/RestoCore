/* Apply saved preferences before first paint to avoid a light/dark flash.
   Loaded as a blocking script in <head> (a file, not inline, so the CSP can forbid inline JS). */
(function () {
  try {
    var t = localStorage.getItem("rc-theme");
    if (!t && window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches) t = "dark";
    if (t) document.documentElement.setAttribute("data-theme", t);
    if (localStorage.getItem("rc-sidebar") === "collapsed") document.documentElement.classList.add("sidebar-collapsed");
  } catch (e) { /* private mode: defaults are fine */ }
})();
