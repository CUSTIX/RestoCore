/* Ask RestoCore: post questions with fetch and render answers in place.
   Answers arrive as plain data (paragraphs, bullet lists, bold runs) and are built with
   textContent, so nothing the model writes can turn into HTML or script. Without JS the form
   still works (normal post + redirect). */
(function () {
  "use strict";
  var root = document.querySelector("[data-ask]");
  var form = root && root.querySelector("[data-ask-form]");
  if (!form) return;
  var log = root.querySelector("[data-ask-log]");
  var input = form.querySelector("textarea");
  var send = form.querySelector("[data-ask-send]");
  var hint = form.querySelector("[data-ask-hint]");
  var defaultHint = hint.textContent;
  var busy = false;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function runs(parent, list) {
    list.forEach(function (run) {
      parent.appendChild(run.bold ? el("strong", null, run.text) : document.createTextNode(run.text));
    });
  }

  function answerNode(blocks) {
    var body = el("div", "ask__body");
    blocks.forEach(function (block) {
      if (block.type === "ul") {
        var ul = el("ul");
        block.items.forEach(function (item) { var li = el("li"); runs(li, item); ul.appendChild(li); });
        body.appendChild(ul);
      } else {
        var p = el("p"); runs(p, block.runs); body.appendChild(p);
      }
    });
    return body;
  }

  function scrollToEnd() {
    var last = log.lastElementChild;
    if (last) last.scrollIntoView({ block: "end", behavior: "smooth" });
  }

  function setBusy(on) {
    busy = on;
    send.disabled = on;
    input.readOnly = on;
    form.classList.toggle("is-busy", on);
  }

  function ask(question) {
    if (busy) return;
    question = question.trim();
    if (!question) { hint.textContent = "Type a question first."; input.focus(); return; }
    var hello = log.querySelector("[data-ask-hello]");
    if (hello) hello.remove();

    var you = el("div", "ask__msg ask__msg--you");
    you.appendChild(el("p", null, question));
    log.appendChild(you);
    var ai = el("div", "ask__msg ask__msg--ai is-thinking");
    var dots = el("div", "ask__thinking");
    dots.setAttribute("aria-label", "Looking it up");
    dots.append(el("span"), el("span"), el("span"));
    ai.appendChild(dots);
    log.appendChild(ai);
    scrollToEnd();

    var data = new FormData(form);
    data.set("question", question);
    input.value = "";
    setBusy(true);
    hint.textContent = "Looking through your data…";

    fetch(form.action || window.location.href, {
      method: "POST",
      body: data,
      headers: { "X-Requested-With": "fetch" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.json().catch(function () { return { error: "Something went wrong. Try again." }; }); })
      .then(function (res) {
        ai.classList.remove("is-thinking");
        ai.textContent = "";
        if (res.error) {
          ai.classList.add("ask__msg--error");
          ai.appendChild(el("p", null, res.error));
          input.value = question; // keep it so they can retry
        } else {
          ai.appendChild(answerNode(res.blocks || []));
          if (res.sources && res.sources.length) {
            ai.appendChild(el("p", "ask__sources", "Looked at: " + res.sources.join(" · ")));
          }
        }
      })
      .catch(function () {
        ai.classList.remove("is-thinking");
        ai.classList.add("ask__msg--error");
        ai.textContent = "";
        ai.appendChild(el("p", null, "Couldn't reach the server. Check your connection and try again."));
        input.value = question;
      })
      .then(function () {
        setBusy(false);
        hint.textContent = defaultHint;
        scrollToEnd();
        input.focus();
      });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault(); // handled here; also tells the shared submit lock to stand down
    ask(input.value);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      ask(input.value);
    }
  });

  root.querySelectorAll("[data-ask-suggest]").forEach(function (chip) {
    chip.addEventListener("click", function () { ask(chip.getAttribute("data-ask-suggest")); });
  });

  if (log.lastElementChild) log.lastElementChild.scrollIntoView({ block: "end" });
})();
