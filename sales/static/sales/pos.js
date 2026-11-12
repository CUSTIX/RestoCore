/* POS: steppers, tap-to-add, live cart and totals, and a Charge button that is only enabled when
   the order can actually go through (and says why when it can't). Quick-cash buttons fill the
   amount received. The server still re-checks everything and recalculates on submit. */
(function () {
  "use strict";
  var form = document.getElementById("pos-form");
  if (!form) return;
  var rate = parseFloat(form.dataset.taxRate || "0");
  var currency = form.dataset.currency || "";
  var MAX_QTY = 99;
  var items = Array.prototype.slice.call(form.querySelectorAll("[data-pos-item]"));
  var cart = document.getElementById("pos-cart");
  var cartEmpty = document.getElementById("pos-cart-empty");
  var charge = document.getElementById("pos-charge");
  var hint = document.getElementById("pos-charge-hint");
  var cashInput = form.querySelector("[name=amount_tendered]");
  var tableInput = form.querySelector("[name=table_label]");
  var quick = form.querySelector("[data-quick-cash]");

  /* Money in whole cents: no floating-point surprises when comparing cash and total. */
  function toCents(value) {
    var n = parseFloat(value);
    return isNaN(n) ? null : Math.round(n * 100);
  }
  function fmt(cents) {
    return currency + (cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function qtyInput(card) { return card.querySelector(".pos-qty"); }
  function maxFor(card) {
    var available = parseInt(card.dataset.available, 10);
    return isNaN(available) ? MAX_QTY : Math.min(MAX_QTY, available);
  }
  function qtyOf(card) { return parseInt(qtyInput(card).value || "0", 10) || 0; }
  function setQty(card, q) {
    var input = qtyInput(card);
    if (!input || input.disabled) return;
    input.value = Math.max(0, Math.min(maxFor(card), q));
    update();
  }
  function radio(name) { return (form.querySelector("[name=" + name + "]:checked") || {}).value; }

  items.forEach(function (card) {
    var input = qtyInput(card);
    card.querySelectorAll("[data-step]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        setQty(card, qtyOf(card) + parseInt(btn.dataset.step, 10));
      });
    });
    card.addEventListener("click", function (e) {
      if (e.target.closest(".stepper")) return;
      setQty(card, qtyOf(card) + 1);
    });
    if (input) {
      input.addEventListener("click", function (e) { e.stopPropagation(); });
      /* Typed quantities are clamped to what's in stock when the cashier leaves the field. */
      input.addEventListener("change", function () { setQty(card, qtyOf(card)); });
    }
  });

  /* Quick cash: rebuilt only when the total changes. Rebuilding on every update would replace
     the button under the pointer when the cash field's "change" (on blur) fires mid-click. */
  var quickFor = null;
  if (quick) {
    quick.addEventListener("click", function (e) {
      var b = e.target.closest("[data-cents]");
      if (!b) return;
      cashInput.value = (parseInt(b.dataset.cents, 10) / 100).toFixed(2);
      update();
    });
  }
  function renderQuickCash(totalCents) {
    if (!quick || totalCents === quickFor) return;
    quickFor = totalCents;
    quick.textContent = "";
    if (totalCents <= 0) return;
    var amounts = [totalCents];
    [5000, 10000, 50000, 100000].forEach(function (step) { /* next 50, 100, 500, 1000 */
      var up = Math.ceil(totalCents / step) * step;
      if (up > totalCents && amounts.indexOf(up) === -1) amounts.push(up);
    });
    amounts.sort(function (a, b) { return a - b; }).slice(0, 4).forEach(function (cents, i) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = i === 0 ? "Exact " + fmt(cents) : fmt(cents);
      b.dataset.cents = cents;
      quick.appendChild(b);
    });
  }

  /* Why the order can't be charged yet, or "" when it can. */
  function blocker(count, totalCents, type, pay, cashCents, overStock) {
    if (count === 0) return "Add a dish to start an order.";
    if (overStock) return "Only " + overStock.max + " × " + overStock.name + " left in stock.";
    if (type === "dine_in" && tableInput && !tableInput.value.trim()) return "Enter the table for a dine-in order.";
    if (pay === "cash") {
      if (cashCents === null) return "Enter the cash received.";
      if (cashCents < totalCents) return "Cash received is " + fmt(totalCents - cashCents) + " short.";
    }
    return "";
  }

  function update() {
    var subCents = 0, count = 0, overStock = null;
    cart.textContent = "";
    items.forEach(function (card) {
      var q = qtyOf(card);
      var priceCents = toCents(card.dataset.price) || 0;
      var max = maxFor(card);
      card.classList.toggle("is-selected", q > 0);
      var badge = card.querySelector("[data-qty-badge]");
      if (badge) badge.textContent = q;
      var plus = card.querySelector('[data-step="1"]'), minus = card.querySelector('[data-step="-1"]');
      if (plus) plus.disabled = q >= max;
      if (minus) minus.disabled = q <= 0;
      if (q > max && !overStock) overStock = { max: max, name: card.dataset.name };
      if (q > 0) {
        count += q;
        subCents += q * priceCents;
        var li = document.createElement("li");
        /* Dish names are typed by managers: insert them as text, never as markup. */
        var label = document.createElement("span");
        var qtyEl = document.createElement("strong");
        qtyEl.textContent = q + "×";
        label.appendChild(qtyEl);
        label.appendChild(document.createTextNode(" " + card.dataset.name));
        var amount = document.createElement("span");
        amount.textContent = fmt(q * priceCents);
        li.appendChild(label);
        li.appendChild(amount);
        cart.appendChild(li);
      }
    });
    cartEmpty.style.display = count ? "none" : "";

    var taxCents = Math.round(subCents * rate);
    var totalCents = subCents + taxCents;
    document.getElementById("pos-subtotal").textContent = fmt(subCents);
    document.getElementById("pos-tax").textContent = fmt(taxCents);
    document.getElementById("pos-total").textContent = fmt(totalCents);

    var bar = document.getElementById("pos-mobile-bar");
    if (bar) {
      bar.classList.toggle("is-on", count > 0);
      document.getElementById("pos-bar-count").textContent = count + (count === 1 ? " item" : " items");
      var barTotal = document.getElementById("pos-bar-total");
      if (barTotal) barTotal.textContent = "Total " + fmt(totalCents);
    }

    var type = radio("order_type"), pay = radio("payment_method");
    form.querySelectorAll("[data-table-field]").forEach(function (el) { el.style.display = type === "takeaway" ? "none" : ""; });
    form.querySelectorAll("[data-cash-field]").forEach(function (el) { el.style.display = pay === "card" ? "none" : ""; });

    var cashCents = cashInput ? toCents(cashInput.value) : null;
    var change = document.getElementById("pos-change");
    var short = cashCents !== null && cashCents < totalCents;
    change.textContent = cashCents === null || !count ? "—" : short ? "Short " + fmt(totalCents - cashCents) : fmt(cashCents - totalCents);
    change.classList.toggle("is-short", short && count > 0);
    renderQuickCash(pay === "cash" ? totalCents : 0);

    var reason = blocker(count, totalCents, type, pay, cashCents, overStock);
    charge.disabled = Boolean(reason);
    hint.textContent = reason || (pay === "cash" ? "Change due: " + fmt(cashCents - totalCents) : "Card payment: " + fmt(totalCents));
    hint.classList.toggle("is-ready", !reason);
  }

  /* One click = one order. (The server is idempotent too: the same screen can't charge twice.) */
  form.addEventListener("submit", function (e) {
    if (charge.disabled) { e.preventDefault(); return; }
    setTimeout(function () {
      charge.disabled = true;
      hint.textContent = "Charging…";
    }, 0);
  });
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
})();
