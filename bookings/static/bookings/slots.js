/* Staff booking form: in the time dropdown, disable times that have passed and mark the ones
   without enough seats for the party, so staff don't learn it only after saving.
   When editing, the booking's own seats don't count against it, and its current date and
   time stay selectable (fixing a phone number on a booking that has started must work). */
(function () {
  "use strict";
  var form = document.querySelector("[data-slot-select]");
  if (!form) return;
  var select = form.querySelector("select[name=time]");
  var dateInput = form.querySelector("input[name=date]");
  var party = form.querySelector("input[name=party_size]");
  var note = form.querySelector("[data-slot-note]");
  if (!select || !dateInput) return;
  var url = form.getAttribute("data-availability-url");
  var exclude = form.getAttribute("data-exclude");
  var keepDate = form.getAttribute("data-keep-date"), keepTime = form.getAttribute("data-keep-time");
  var seats = null, asked = "";

  function apply() {
    if (!seats) return;
    var size = parseInt((party || {}).value, 10) || 1, open = 0;
    Array.prototype.forEach.call(select.options, function (opt) {
      if (!opt.value) return;
      if (!opt.dataset.label) opt.dataset.label = opt.textContent;
      var left = seats[opt.value];
      var own = dateInput.value === keepDate && opt.value === keepTime;
      var ok = own || (left !== null && left !== undefined && left >= size);
      opt.disabled = !ok;
      opt.textContent = opt.dataset.label + (ok ? "" : left === null || left === undefined ? " (passed)" : left === 0 ? " (full)" : " (" + left + " left)");
      if (ok) open++;
    });
    if (select.selectedOptions[0] && select.selectedOptions[0].disabled) select.value = "";
    var anyAhead = Array.prototype.some.call(select.options, function (o) { return o.value && seats[o.value] !== null && seats[o.value] !== undefined; });
    note.textContent = open ? "" : anyAhead ? "No time on this day has room for " + size + (size === 1 ? " guest." : " guests.") : "All times on this day have passed. Pick another date.";
  }
  function load() {
    var day = dateInput.value;
    if (!day) return;
    if (day === asked) return apply();
    asked = day;
    var q = "?date=" + encodeURIComponent(day) + (exclude ? "&exclude=" + encodeURIComponent(exclude) : "");
    fetch(url + q, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data && data.date === dateInput.value) { seats = data.seats; apply(); } })
      .catch(function () { /* the server still validates on save */ });
  }
  dateInput.addEventListener("change", load);
  if (party) party.addEventListener("input", apply);
  load();
})();
