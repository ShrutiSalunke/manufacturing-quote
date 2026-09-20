/**
 * Quote wizard — Weight calculator (shape picker + dimension form).
 */
(function (global) {
  "use strict";

  var UNIT_OPTS = ["mm", "cm", "m", "in", "ft"];

  var ICONS = {
    round_bar:
      '<svg viewBox="0 0 64 64" fill="none"><ellipse cx="32" cy="18" rx="14" ry="6" stroke="#4b5563" stroke-width="2"/><path d="M18 18v28c0 3.3 6.3 6 14 6s14-2.7 14-6V18" stroke="#4b5563" stroke-width="2"/><ellipse cx="32" cy="46" rx="14" ry="6" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/></svg>',
    pipe:
      '<svg viewBox="0 0 64 64" fill="none"><ellipse cx="32" cy="18" rx="14" ry="6" stroke="#4b5563" stroke-width="2"/><ellipse cx="32" cy="18" rx="7" ry="3" stroke="#4b5563" stroke-width="2"/><path d="M18 18v28c0 3.3 6.3 6 14 6s14-2.7 14-6V18M25 18v28" stroke="#4b5563" stroke-width="2"/><ellipse cx="32" cy="46" rx="14" ry="6" stroke="#4b5563" stroke-width="2"/></svg>',
    square_bar:
      '<svg viewBox="0 0 64 64" fill="none"><path d="M18 22h28v28H18z" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/><path d="M18 22l8-8h28l-8 8M46 22v28l8-8V14L46 22z" stroke="#4b5563" stroke-width="2"/></svg>',
    hex_bar:
      '<svg viewBox="0 0 64 64" fill="none"><path d="M32 12l14 8v16l-14 8-14-8V20l14-8z" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/></svg>',
    square_tubing:
      '<svg viewBox="0 0 64 64" fill="none"><rect x="14" y="18" width="36" height="36" stroke="#4b5563" stroke-width="2"/><rect x="22" y="26" width="20" height="20" stroke="#4b5563" stroke-width="2" fill="#f3f4f6"/></svg>',
    beam:
      '<svg viewBox="0 0 64 64" fill="none"><path d="M14 16h36v8H38v24h12v8H14v-8h12V24H14v-8z" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/></svg>',
    t_bar:
      '<svg viewBox="0 0 64 64" fill="none"><path d="M12 16h40v10H38v30H26V26H12V16z" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/></svg>',
    channel:
      '<svg viewBox="0 0 64 64" fill="none"><path d="M18 14h28v10H28v24h18v10H18V14z" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/></svg>',
    angle:
      '<svg viewBox="0 0 64 64" fill="none"><path d="M16 14h12v28h28v12H16V14z" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/></svg>',
    flat_bar:
      '<svg viewBox="0 0 64 64" fill="none"><rect x="10" y="28" width="44" height="12" rx="1" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/></svg>',
    sheet:
      '<svg viewBox="0 0 64 64" fill="none"><path d="M14 20h30l6 6v26H14V20z" stroke="#4b5563" stroke-width="2" fill="#e5e7eb"/><path d="M44 20v6h6" stroke="#4b5563" stroke-width="2"/></svg>',
  };

  function readJson(id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent);
    } catch (e) {
      return fallback;
    }
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function init(opts) {
    var form = document.getElementById(opts.formId);
    if (!form) return;

    var shapes = readJson("mq-weight-shapes", []);
    var metals = readJson("mq-metal-options", []);
    var saved = readJson("mq-weight-saved", {}) || {};
    var shapeById = {};
    shapes.forEach(function (s) {
      shapeById[s.id] = s;
    });

    var shapeInput = document.getElementById("id_shape_id");
    var materialInput = document.getElementById("id_material_id");
    var presetInput = document.getElementById("id_preset_name");
    var metalLabelInput = document.getElementById("id_metal_label");
    var metalSelect = document.getElementById("id_metal_select");
    var densityInput = document.getElementById("id_density");
    var picker = document.getElementById("mq-weight-picker");
    var calc = document.getElementById("mq-weight-calc");
    var dimFields = document.getElementById("mq-weight-dim-fields");
    var diagram = document.getElementById("mq-weight-diagram");
    var shapeTitle = document.getElementById("mq-weight-shape-title");
    var targetWrap = document.getElementById("mq-target-weight-wrap");
    var changeBtn = document.getElementById("mq-weight-change-shape");

    function fillMetalSelect(selectedId) {
      var html = '<option value="">Select material…</option>';
      if (!metals.length) {
        metalSelect.innerHTML = html;
        materialInput.value = "";
        metalLabelInput.value = "";
        return;
      }
      metals.forEach(function (m, idx) {
        var sel =
          (selectedId && String(m.id) === String(selectedId)) ||
          (!selectedId && idx === 0);
        html +=
          '<option value="' +
          m.id +
          '" data-density="' +
          m.density +
          '" data-price="' +
          (m.unit_price || 0) +
          '"' +
          (sel ? " selected" : "") +
          ">" +
          escapeHtml(m.label) +
          "</option>";
      });
      metalSelect.innerHTML = html;
      applyMetalSelection();
    }

    function applyMetalSelection() {
      var opt = metalSelect.options[metalSelect.selectedIndex];
      if (!opt || !opt.value) {
        materialInput.value = "";
        metalLabelInput.value = "";
        return;
      }
      densityInput.value = opt.getAttribute("data-density") || "7.85";
      var price = opt.getAttribute("data-price");
      var priceEl = document.getElementById("id_price_per_kg");
      if (priceEl && price && (!priceEl.value || priceEl.value === "0")) {
        priceEl.value = price;
      }
      materialInput.value = opt.value;
      metalLabelInput.value = opt.textContent.trim();
      if (presetInput) presetInput.value = "";
    }

    function renderDims(shape, values, units) {
      values = values || {};
      units = units || {};
      dimFields.innerHTML = "";
      (shape.fields || []).forEach(function (f) {
        var unitOpts = UNIT_OPTS.map(function (u) {
          return (
            '<option value="' +
            u +
            '"' +
            ((units[f.key] || "mm") === u ? " selected" : "") +
            ">" +
            u +
            "</option>"
          );
        }).join("");
        dimFields.insertAdjacentHTML(
          "beforeend",
          '<div class="col-md-6 mq-dim-row" data-dim-key="' +
            escapeHtml(f.key) +
            '">' +
            '<label class="form-label">' +
            escapeHtml(f.label) +
            "</label>" +
            '<div class="input-group">' +
            '<input type="number" step="any" class="form-control mq-input" name="dim_' +
            escapeHtml(f.key) +
            '" value="' +
            escapeHtml(values[f.key] != null ? values[f.key] : "") +
            '">' +
            '<select class="form-select" name="unit_' +
            escapeHtml(f.key) +
            '" style="max-width:5.5rem">' +
            unitOpts +
            "</select></div></div>"
        );
      });
      syncModeUI();
    }

    function syncModeUI() {
      var mode =
        (form.querySelector('input[name="mode"]:checked') || {}).value || "by_length";
      var lengthRow = dimFields.querySelector('[data-dim-key="length"]');
      if (mode === "by_weight") {
        targetWrap.classList.remove("d-none");
        if (lengthRow) lengthRow.classList.add("d-none");
      } else {
        targetWrap.classList.add("d-none");
        if (lengthRow) lengthRow.classList.remove("d-none");
      }
    }

    function openShape(shapeId) {
      var shape = shapeById[shapeId];
      if (!shape) return;
      shapeInput.value = shapeId;
      shapeTitle.textContent = shape.label;
      diagram.innerHTML = ICONS[shape.diagram] || ICONS.round_bar;
      if (picker) {
        picker.classList.add("d-none");
        picker.setAttribute("hidden", "hidden");
      }
      if (calc) {
        calc.classList.remove("d-none");
        calc.removeAttribute("hidden");
      }
      var dims = (saved && saved.dimensions) || {};
      var units = (saved && saved.units) || {};
      if (saved && saved.result && saved.result.shape_id !== shapeId) {
        dims = {};
        units = {};
      }
      renderDims(shape, dims, units);
    }

    function showPicker() {
      shapeInput.value = "";
      if (picker) {
        picker.classList.remove("d-none");
        picker.removeAttribute("hidden");
      }
      if (calc) {
        calc.classList.add("d-none");
        calc.setAttribute("hidden", "hidden");
      }
    }

    // Paint icons in picker
    form.querySelectorAll(".mq-weight-shape-icon").forEach(function (el) {
      var key = el.getAttribute("data-icon");
      el.innerHTML = ICONS[key] || ICONS.round_bar;
    });

    form.querySelectorAll(".mq-weight-shape-card").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openShape(btn.getAttribute("data-shape-id"));
      });
    });

    if (changeBtn) changeBtn.addEventListener("click", showPicker);
    metalSelect.addEventListener("change", applyMetalSelection);
    form.querySelectorAll('input[name="mode"]').forEach(function (r) {
      r.addEventListener("change", syncModeUI);
    });

    // Restore saved
    var savedMatId = saved.material_id || "";
    fillMetalSelect(savedMatId);
    if (saved.density != null) densityInput.value = saved.density;
    if (saved.pieces != null) document.getElementById("id_pieces").value = saved.pieces;
    if (saved.price_per_kg != null)
      document.getElementById("id_price_per_kg").value = saved.price_per_kg;
    if (saved.target_weight_kg != null)
      document.getElementById("id_target_weight_kg").value = saved.target_weight_kg;
    if (saved.mode) {
      var modeRadio = form.querySelector('input[name="mode"][value="' + saved.mode + '"]');
      if (modeRadio) modeRadio.checked = true;
    }

    var initialShape = opts.savedShape || shapeInput.value || "";
    if (initialShape && shapeById[initialShape]) {
      openShape(initialShape);
    }

    form.addEventListener("submit", function (ev) {
      var submitter = ev.submitter;
      var action = submitter && submitter.name === "wizard_action" ? submitter.value : "";
      if (action === "back" || action === "clear_weight" || action === "next") {
        // next without shape is allowed (skip)
        if (action === "next" && !shapeInput.value) return;
        if (action === "back" || action === "clear_weight") {
          form.querySelectorAll("[required]").forEach(function (n) {
            n.removeAttribute("required");
          });
        }
      }
      if ((action === "calculate" || action === "save_weight") && !shapeInput.value) {
        ev.preventDefault();
        alert("Select a raw material shape first.");
      }
    });
  }

  global.MQWizardWeight = { init: init };
})(window);
