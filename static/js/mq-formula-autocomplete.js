/**
 * Autocomplete for process/subprocess result_formula from Fields section codes.
 * Usage: MQ.initFormulaAutocomplete({ form: formEl });
 */
(function () {
  window.MQ = window.MQ || {};

  var TOKEN_RE = /[A-Za-z_][A-Za-z0-9_]*$/;

  function collectFieldCodes(fieldRows) {
    if (!fieldRows) return [];
    var codes = [];
    var seen = {};
    fieldRows.querySelectorAll(".mq-inline-field-row:not(.is-removed)").forEach(function (row) {
      var input = row.querySelector('input[name$="-code"]');
      if (!input) return;
      var code = (input.value || "").trim().toUpperCase();
      if (!code || seen[code]) return;
      seen[code] = true;
      codes.push(code);
    });
    codes.sort();
    return codes;
  }

  function tokenAtCursor(value, cursor) {
    var before = value.slice(0, cursor);
    var match = before.match(TOKEN_RE);
    if (!match) return { start: cursor, end: cursor, text: "" };
    return {
      start: cursor - match[0].length,
      end: cursor,
      text: match[0],
    };
  }

  function ensureSuggestList(wrap) {
    var list = wrap.querySelector(".mq-formula-suggest");
    if (list) return list;
    list = document.createElement("ul");
    list.className = "mq-formula-suggest";
    list.hidden = true;
    list.setAttribute("role", "listbox");
    wrap.appendChild(list);
    return list;
  }

  MQ.initFormulaAutocomplete = function (opts) {
    opts = opts || {};
    var form = opts.form;
    if (!form) return;

    var formula = form.querySelector("#id_result_formula");
    var fieldRows = document.getElementById("mq-field-rows");
    if (!formula || !fieldRows) return;

    var wrap = formula.closest(".mq-field") || formula.parentElement;
    wrap.classList.add("mq-formula-wrap");
    var list = ensureSuggestList(wrap);
    var activeIndex = -1;
    var currentItems = [];

    var hint = wrap.querySelector(".mq-formula-ac-hint");
    if (!hint) {
      hint = document.createElement("div");
      hint.className = "mq-help mq-formula-ac-hint";
      hint.textContent =
        "Start typing a field Code for suggestions (↑↓ to move, Enter/Tab to insert).";
      formula.insertAdjacentElement("afterend", hint);
    }

    function hide() {
      list.hidden = true;
      list.innerHTML = "";
      activeIndex = -1;
      currentItems = [];
    }

    function render(items, query) {
      currentItems = items;
      activeIndex = items.length ? 0 : -1;
      if (!items.length) {
        hide();
        return;
      }
      list.innerHTML = "";
      items.forEach(function (code, i) {
        var li = document.createElement("li");
        li.className = "mq-formula-suggest-item" + (i === 0 ? " is-active" : "");
        li.setAttribute("role", "option");
        li.dataset.code = code;
        li.textContent = code;
        if (query) {
          // keep plain text; highlight via CSS only on active
        }
        list.appendChild(li);
      });
      list.hidden = false;
    }

    function setActive(index) {
      var nodes = list.querySelectorAll(".mq-formula-suggest-item");
      if (!nodes.length) return;
      activeIndex = (index + nodes.length) % nodes.length;
      nodes.forEach(function (n, i) {
        n.classList.toggle("is-active", i === activeIndex);
      });
      nodes[activeIndex].scrollIntoView({ block: "nearest" });
    }

    function insertCode(code) {
      var start = formula.selectionStart || 0;
      var end = formula.selectionEnd || 0;
      var value = formula.value || "";
      var token = tokenAtCursor(value, start);
      var next =
        value.slice(0, token.start) + code + value.slice(Math.max(end, token.end));
      formula.value = next;
      var caret = token.start + code.length;
      formula.focus();
      formula.setSelectionRange(caret, caret);
      hide();
      formula.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function updateSuggestions() {
      var start = formula.selectionStart || 0;
      var token = tokenAtCursor(formula.value || "", start);
      var q = (token.text || "").toUpperCase();
      // Show all codes when empty token after operator/space, or filter by prefix
      var codes = collectFieldCodes(fieldRows);
      if (!codes.length) {
        hide();
        return;
      }
      // Only open when user is typing an identifier-ish token, or Ctrl+Space handled separately
      if (!token.text) {
        hide();
        return;
      }
      var filtered = codes.filter(function (c) {
        return c.indexOf(q) === 0;
      });
      render(filtered, q);
    }

    function showAll() {
      var codes = collectFieldCodes(fieldRows);
      if (!codes.length) {
        hide();
        return;
      }
      render(codes, "");
    }

    formula.addEventListener("input", updateSuggestions);
    formula.addEventListener("click", updateSuggestions);
    formula.addEventListener("keyup", function (e) {
      if (["ArrowUp", "ArrowDown", "Enter", "Tab", "Escape"].indexOf(e.key) !== -1) return;
      updateSuggestions();
    });

    formula.addEventListener("keydown", function (e) {
      if (e.key === " " && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        showAll();
        return;
      }
      if (list.hidden) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive(activeIndex + 1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive(activeIndex - 1);
      } else if (e.key === "Enter" || e.key === "Tab") {
        if (activeIndex >= 0 && currentItems[activeIndex]) {
          e.preventDefault();
          insertCode(currentItems[activeIndex]);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        hide();
      }
    });

    list.addEventListener("mousedown", function (e) {
      var item = e.target.closest(".mq-formula-suggest-item");
      if (!item) return;
      e.preventDefault();
      insertCode(item.dataset.code);
    });

    formula.addEventListener("blur", function () {
      setTimeout(hide, 150);
    });

    // Refresh suggestions when field codes change
    fieldRows.addEventListener("input", function (e) {
      if (e.target && e.target.name && e.target.name.indexOf("-code") !== -1) {
        if (!list.hidden) updateSuggestions();
      }
    });
  };
})();
