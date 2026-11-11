/* POS: steppers, tap-to-add, live cart and totals. The server always recalculates on submit. */
(function () {
  "use strict";
  var form = document.getElementById("pos-form");
  if (!form) return;
  var rate = parseFloat(form.dataset.taxRate || "0");
  var currency = form.dataset.currency || "";
  var fmt = function (n) { return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
  var items = Array.prototype.slice.call(form.querySelectorAll("[data-pos-item]"));
  var cart = document.getElementById("pos-cart");
  var cartEmpty = document.getElementById("pos-cart-empty");

  function qtyInput(card) { return card.querySelector(".pos-qty"); }
  function setQty(card, q) {
    var input = qtyInput(card);
    if (!input || input.disabled) return;
    input.value = Math.max(0, Math.min(99, q));
    update();
  }

  items.forEach(function (card) {
    var input = qtyInput(card);
    card.querySelectorAll("[data-step]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        setQty(card, (parseInt(input.value, 10) || 0) + parseInt(btn.dataset.step, 10));
      });
    });
    card.addEventListener("click", function (e) {
      if (e.target.closest(".stepper")) return;
      setQty(card, (parseInt(input.value, 10) || 0) + 1);
    });
    if (input) input.addEventListener("click", function (e) { e.stopPropagation(); });
  });

  function update() {
    var sub = 0;
    cart.innerHTML = "";
    items.forEach(function (card) {
      var q = parseInt(qtyInput(card).value || "0", 10) || 0;
      var price = parseFloat(card.dataset.price);
      card.classList.toggle("is-selected", q > 0);
      var badge = card.querySelector("[data-qty-badge]");
      if (badge) badge.textContent = q;
      if (q > 0) {
        sub += q * price;
        var li = document.createElement("li");
        li.innerHTML = "<span><strong>" + q + "×</strong> " + card.dataset.name.replace(/</g, "&lt;") + "</span><span>" + fmt(q * price) + "</span>";
        cart.appendChild(li);
      }
    });
    cartEmpty.style.display = cart.children.length ? "none" : "";
    var tax = Math.round(sub * rate * 100) / 100;
    var total = sub + tax;
    document.getElementById("pos-subtotal").textContent = currency + fmt(sub);
    document.getElementById("pos-tax").textContent = currency + fmt(tax);
    document.getElementById("pos-total").textContent = currency + fmt(total);
    var cash = parseFloat((form.querySelector("[name=amount_tendered]") || {}).value || "");
    var change = document.getElementById("pos-change");
    change.textContent = isNaN(cash) ? "—" : currency + fmt(cash - total);
    change.style.color = !isNaN(cash) && cash < total ? "var(--danger)" : "";

    var type = (form.querySelector("[name=order_type]:checked") || {}).value;
    form.querySelectorAll("[data-table-field]").forEach(function (el) { el.style.display = type === "takeaway" ? "none" : ""; });
    var pay = (form.querySelector("[name=payment_method]:checked") || {}).value;
    form.querySelectorAll("[data-cash-field]").forEach(function (el) { el.style.display = pay === "card" ? "none" : ""; });
  }

  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
})();
