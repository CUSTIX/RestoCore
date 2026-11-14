/* Customer self-ordering: +/- steppers, a live count and estimate in the bottom bar, and a
   "Done ordering" button that is only enabled once something is picked. Works without JS too
   (plain number inputs); the server re-checks and re-prices everything. */
(function () {
  "use strict";
  var form = document.querySelector("[data-self-order]");
  if (!form) return;
  var rate = parseFloat(form.dataset.taxRate || "0");
  var currency = form.dataset.currency || "";
  var MAX_QTY = 99;
  var items = Array.prototype.slice.call(form.querySelectorAll("[data-order-item]"));
  var submit = form.querySelector("[data-order-submit]");
  var countEl = form.querySelector("[data-order-count]");
  var totalEl = form.querySelector("[data-order-total]");
  var tableInput = form.querySelector("[name=table_label]");

  function toCents(value) { var n = parseFloat(value); return isNaN(n) ? 0 : Math.round(n * 100); }
  function fmt(cents) {
    return currency + (cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function input(card) { return card.querySelector("input[type=number]"); }
  function qtyOf(card) { return parseInt(input(card).value || "0", 10) || 0; }
  function setQty(card, q) {
    var el = input(card);
    if (el.disabled) return;
    el.value = Math.max(0, Math.min(MAX_QTY, q));
    update();
  }
  function orderType() { return (form.querySelector("[name=order_type]:checked") || {}).value; }

  items.forEach(function (card) {
    card.querySelectorAll("[data-step]").forEach(function (btn) {
      btn.addEventListener("click", function () { setQty(card, qtyOf(card) + parseInt(btn.dataset.step, 10)); });
    });
    input(card).addEventListener("change", function () { setQty(card, qtyOf(card)); });
  });

  function update() {
    var count = 0, sub = 0;
    items.forEach(function (card) {
      var q = qtyOf(card), el = input(card);
      count += q;
      sub += q * toCents(card.dataset.price);
      card.classList.toggle("is-selected", q > 0);
      var minus = card.querySelector('[data-step="-1"]'), plus = card.querySelector('[data-step="1"]');
      if (minus) minus.disabled = q <= 0 || el.disabled;
      if (plus) plus.disabled = q >= MAX_QTY || el.disabled;
    });
    var takeaway = orderType() === "takeaway";
    form.querySelectorAll("[data-table-field]").forEach(function (el) { el.hidden = takeaway; });
    var needsTable = !takeaway && tableInput && !tableInput.value.trim();
    countEl.textContent = count ? count + (count === 1 ? " item" : " items") : "Nothing yet";
    totalEl.textContent = count
      ? (needsTable ? "Enter your table number above" : "About " + fmt(sub + Math.round(sub * rate)) + " with tax")
      : "Tap + to add a dish";
    submit.disabled = !count || needsTable;
  }

  form.addEventListener("submit", function (e) {
    if (submit.disabled) { e.preventDefault(); return; }
    setTimeout(function () { submit.disabled = true; }, 0);  /* one tap, one order */
  });
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
})();
