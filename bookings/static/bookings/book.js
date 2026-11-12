/* Booking form enhancements: time-slot chips and a party-size stepper.
   The original <select> and <input> stay in the form, so it still works without JavaScript. */
(function () {
  "use strict";
  var form = document.querySelector("[data-booking-form]");
  if (!form) return;

  var select = form.querySelector("select[name=time]");
  if (select) {
    var group = document.createElement("div");
    group.className = "slots";
    group.setAttribute("role", "radiogroup");
    group.setAttribute("aria-label", "Time");
    Array.prototype.forEach.call(select.options, function (opt) {
      if (!opt.value) return;
      var label = document.createElement("label");
      label.className = "slot";
      /* Built with DOM calls, not innerHTML, so option text can never become markup. */
      var radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "__slot";
      radio.value = opt.value;
      var text = document.createElement("span");
      text.textContent = opt.textContent;
      label.appendChild(radio);
      label.appendChild(text);
      radio.checked = opt.selected && select.value === opt.value;
      radio.addEventListener("change", function () { select.value = opt.value; });
      group.appendChild(label);
    });
    select.classList.add("sr-only");
    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");
    select.parentNode.insertBefore(group, select.nextSibling);
    if (!select.value || !group.querySelector("input:checked")) {
      var first = group.querySelector('input[value="18:00"]') || group.querySelector("input");
      if (first && !form.querySelector(".field--error")) { first.checked = true; select.value = first.value; }
    }
  }

  var party = form.querySelector("input[name=party_size]");
  if (party) {
    var wrap = document.createElement("div");
    wrap.className = "party";
    party.parentNode.insertBefore(wrap, party);
    var minus = document.createElement("button"), plus = document.createElement("button");
    minus.type = plus.type = "button";
    minus.setAttribute("aria-label", "Fewer guests"); plus.setAttribute("aria-label", "More guests");
    minus.textContent = "−"; plus.textContent = "+";
    wrap.appendChild(minus); wrap.appendChild(party); wrap.appendChild(plus);
    if (!party.value) party.value = 2;
    var clamp = function (v) { return Math.max(1, Math.min(20, v)); };
    var bump = function (d) {
      party.value = clamp((parseInt(party.value, 10) || 2) + d);
      party.dispatchEvent(new Event("input", { bubbles: true }));  /* re-check which times fit */
    };
    minus.addEventListener("click", function () { bump(-1); });
    plus.addEventListener("click", function () { bump(1); });
  }

  /* Availability: hide times that have passed on the chosen day and grey out the ones without
     enough seats for this party, so guests only pick what can actually be booked. The server
     still checks on submit (someone else may book the last seats in between). */
  var url = form.getAttribute("data-availability-url");
  var dateInput = form.querySelector("input[name=date]");
  if (!url || !dateInput || !select || !group) return;
  var note = document.createElement("p");
  note.className = "slots__note";
  note.setAttribute("aria-live", "polite");
  group.parentNode.insertBefore(note, group.nextSibling);
  var seats = null, asked = "";

  function apply() {
    if (!seats) return;
    var size = parseInt((party || {}).value, 10) || 1, open = 0;
    group.querySelectorAll("input[type=radio]").forEach(function (radio) {
      var label = radio.parentNode, left = seats[radio.value];
      var passed = left === null || left === undefined, fits = !passed && left >= size;
      label.hidden = passed;
      radio.disabled = !fits;
      label.classList.toggle("is-full", !passed && !fits);
      label.title = passed ? "" : fits ? (left < 10 ? left + " seats left" : "") : left === 0 ? "Fully booked" : "Only " + left + " seats left";
      if (fits) open++;
      if (radio.checked && !fits) radio.checked = false;
    });
    if (!group.querySelector("input:checked")) {
      var pick = group.querySelector('input[value="18:00"]:not(:disabled)') || group.querySelector("input:not(:disabled)");
      if (pick) { pick.checked = true; select.value = pick.value; } else { select.value = ""; }
    }
    note.textContent = open ? "" : "No tables left for " + size + (size === 1 ? " guest" : " guests") + " on this day. Please try another date or call us.";
  }
  function load() {
    var day = dateInput.value;
    if (!day || day === asked) return apply();
    asked = day;
    fetch(url + "?date=" + encodeURIComponent(day), { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data && data.date === dateInput.value) { seats = data.seats; apply(); } })
      .catch(function () { /* offline: the server still validates on submit */ });
  }
  dateInput.addEventListener("change", load);
  if (party) party.addEventListener("input", apply);
  load();
})();
