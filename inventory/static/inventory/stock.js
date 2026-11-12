/* Stock form on an inventory item: the quantity limits follow the chosen action, so the form
   explains a bad number before it is sent (the server enforces the same rules).
     receive  more than zero
     waste    more than zero, at most what is on hand
     count    zero or more (the exact quantity counted)                                       */
(function () {
  "use strict";
  var form = document.querySelector("[data-stock-form]");
  if (!form) return;
  var action = form.elements.action, qty = form.elements.quantity;
  var hint = form.querySelector("[data-stock-hint]");
  if (!action || !qty) return;
  var onHand = parseFloat(form.dataset.onHand), unit = form.dataset.unit || "";
  var fmt = function (n) { return n.toLocaleString(undefined, { maximumFractionDigits: 3 }) + " " + unit; };

  function apply() {
    var a = action.value;
    qty.min = a === "count" ? "0" : "0.001";
    if (a === "waste") {
      qty.max = String(onHand);
      qty.setAttribute("data-max-message", "Only " + fmt(onHand) + " on hand: you can't waste more than that.");
    } else {
      qty.removeAttribute("max");
      qty.removeAttribute("data-max-message");
    }
    var n = parseFloat(qty.value);
    if (a === "receive") hint.textContent = isNaN(n) ? "On hand: " + fmt(onHand) : "After receiving: " + fmt(onHand + n);
    else if (a === "waste") hint.textContent = isNaN(n) || n > onHand ? "On hand: " + fmt(onHand) : "After waste: " + fmt(onHand - n);
    else hint.textContent = isNaN(n) ? "On hand now: " + fmt(onHand) : "Change: " + (n - onHand >= 0 ? "+" : "") + fmt(n - onHand);
  }
  action.addEventListener("change", apply);
  qty.addEventListener("input", apply);
  apply();
})();
