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
      label.innerHTML = '<input type="radio" name="__slot" value="' + opt.value + '"><span>' + opt.textContent + "</span>";
      var radio = label.querySelector("input");
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
    minus.addEventListener("click", function () { party.value = clamp((parseInt(party.value, 10) || 2) - 1); });
    plus.addEventListener("click", function () { party.value = clamp((parseInt(party.value, 10) || 2) + 1); });
  }
})();
