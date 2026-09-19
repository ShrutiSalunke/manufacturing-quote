/**
 * Quote wizard — typeahead on Client code / Company name; autofill + lock other fields.
 */
(function (global) {
  "use strict";

  var FIELD_NAMES = [
    "code",
    "company",
    "name",
    "email",
    "phone",
    "gstin",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country",
  ];
  var SEARCH_FIELDS = ["code", "company"];

  function $(id) {
    return document.getElementById(id);
  }

  function fieldEl(name) {
    return document.getElementById("id_" + name);
  }

  function setLocked(locked, changeBtn) {
    FIELD_NAMES.forEach(function (name) {
      var el = fieldEl(name);
      if (!el) return;
      if (locked) {
        el.setAttribute("readonly", "readonly");
        el.classList.add("is-locked");
      } else {
        el.removeAttribute("readonly");
        el.classList.remove("is-locked");
      }
    });
    if (changeBtn) {
      changeBtn.classList.toggle("d-none", !locked);
    }
  }

  function fillClient(data) {
    FIELD_NAMES.forEach(function (name) {
      var el = fieldEl(name);
      if (!el) return;
      var val = data[name];
      el.value = val == null ? "" : String(val);
    });
  }

  function clearClientFields() {
    FIELD_NAMES.forEach(function (name) {
      var el = fieldEl(name);
      if (!el) return;
      if (name === "country") el.value = "India";
      else el.value = "";
    });
  }

  function init(opts) {
    var form = $(opts.formId);
    if (!form) return;

    var suggestUrl = form.getAttribute("data-client-suggest-url");
    var customerId = $("id_customer_id");
    var changeBtn = $("mq-client-change");
    var fieldsJson = $("mq-client-field-names");
    if (fieldsJson) {
      try {
        var parsed = JSON.parse(fieldsJson.textContent);
        if (Array.isArray(parsed) && parsed.length) {
          FIELD_NAMES.length = 0;
          parsed.forEach(function (n) {
            FIELD_NAMES.push(n);
          });
        }
      } catch (e) {
        /* keep defaults */
      }
    }

    var locked = !!opts.locked;
    setLocked(locked, changeBtn);

    var activeWrap = null;
    var activeIndex = -1;
    var results = [];
    var timer = null;

    function hideAllSuggest() {
      form.querySelectorAll(".mq-client-suggest").forEach(function (list) {
        list.hidden = true;
        list.innerHTML = "";
      });
      activeWrap = null;
      activeIndex = -1;
      results = [];
    }

    function showSuggest(wrap, items) {
      var list = wrap.querySelector(".mq-client-suggest");
      results = items || [];
      activeWrap = wrap;
      activeIndex = -1;
      if (!list || !results.length) {
        if (list) {
          list.hidden = true;
          list.innerHTML = "";
        }
        return;
      }
      list.innerHTML = "";
      results.forEach(function (item, idx) {
        var li = document.createElement("li");
        li.className = "mq-client-suggest-item";
        li.setAttribute("role", "option");
        li.textContent = item.label;
        li.addEventListener("mousedown", function (ev) {
          ev.preventDefault();
          selectItem(item);
        });
        list.appendChild(li);
      });
      list.hidden = false;
    }

    function selectItem(item) {
      if (!item) return;
      if (customerId) customerId.value = String(item.id);
      fillClient(item);
      locked = true;
      setLocked(true, changeBtn);
      hideAllSuggest();
    }

    function unlockForNew(keepValues) {
      if (customerId) customerId.value = "";
      locked = false;
      setLocked(false, changeBtn);
      if (!keepValues) clearClientFields();
    }

    function fetchSuggest(wrap, q, field) {
      if (!suggestUrl) return;
      var url =
        suggestUrl +
        (suggestUrl.indexOf("?") >= 0 ? "&" : "?") +
        "q=" +
        encodeURIComponent(q) +
        "&field=" +
        encodeURIComponent(field);
      fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          showSuggest(wrap, (data && data.results) || []);
        })
        .catch(function () {
          hideAllSuggest();
        });
    }

    function bindSearchField(fieldName) {
      var input = fieldEl(fieldName);
      var wrap = form.querySelector('.mq-client-typeahead[data-suggest-field="' + fieldName + '"]');
      if (!input || !wrap) return;

      input.addEventListener("input", function () {
        if (locked) return;
        var q = input.value.trim();
        clearTimeout(timer);
        if (q.length < 1) {
          hideAllSuggest();
          return;
        }
        timer = setTimeout(function () {
          fetchSuggest(wrap, q, fieldName);
        }, 220);
      });

      input.addEventListener("keydown", function (ev) {
        var list = wrap.querySelector(".mq-client-suggest");
        if (!list || list.hidden || !results.length || activeWrap !== wrap) return;
        var items = list.querySelectorAll(".mq-client-suggest-item");
        if (ev.key === "ArrowDown") {
          ev.preventDefault();
          activeIndex = Math.min(activeIndex + 1, items.length - 1);
        } else if (ev.key === "ArrowUp") {
          ev.preventDefault();
          activeIndex = Math.max(activeIndex - 1, 0);
        } else if (ev.key === "Enter" && activeIndex >= 0) {
          ev.preventDefault();
          selectItem(results[activeIndex]);
          return;
        } else if (ev.key === "Escape") {
          hideAllSuggest();
          return;
        } else {
          return;
        }
        items.forEach(function (el, i) {
          el.classList.toggle("is-active", i === activeIndex);
        });
      });

      input.addEventListener("blur", function () {
        setTimeout(hideAllSuggest, 150);
      });

      input.addEventListener("focus", function () {
        if (locked) return;
        var q = input.value.trim();
        if (q.length >= 1) fetchSuggest(wrap, q, fieldName);
      });
    }

    SEARCH_FIELDS.forEach(bindSearchField);

    if (changeBtn) {
      changeBtn.addEventListener("click", function () {
        unlockForNew(false);
        var code = fieldEl("code");
        if (code) code.focus();
      });
    }
  }

  global.MQWizardClient = { init: init };
})(window);
