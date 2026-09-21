/**
 * Quote wizard Step 2 — multiple process blocks; subprocesses via dropdowns.
 */
(function (global) {
  "use strict";

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function readJson(id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent);
    } catch (e) {
      return fallback;
    }
  }

  function fieldInputHtml(f, name, value) {
    var val = value != null && value !== "" ? value : f.default_value || "";
    var req = f.is_required ? "required" : "";
    var help = [];
    if (f.unit) help.push(f.unit);
    if (f.help_text) help.push(f.help_text);
    var helpHtml = help.length
      ? '<div class="form-text">' + escapeHtml(help.join(" — ")) + "</div>"
      : "";
    if (f.data_type === "bool") {
      var checked = String(val) === "1" || String(val).toLowerCase() === "true" ? " checked" : "";
      return (
        '<div class="col-md-6"><div class="form-check mt-2">' +
        '<input class="form-check-input" type="checkbox" name="' +
        escapeHtml(name) +
        '" id="' +
        escapeHtml(name) +
        '" value="1"' +
        checked +
        ">" +
        '<label class="form-check-label" for="' +
        escapeHtml(name) +
        '">' +
        escapeHtml(f.label) +
        "</label></div>" +
        helpHtml +
        "</div>"
      );
    }
    var type = f.data_type === "number" ? "number" : "text";
    var step = f.data_type === "number" ? ' step="any"' : "";
    var min = f.min_value != null ? ' min="' + escapeHtml(f.min_value) + '"' : "";
    var max = f.max_value != null ? ' max="' + escapeHtml(f.max_value) + '"' : "";
    return (
      '<div class="col-md-6">' +
      '<label class="form-label" for="' +
      escapeHtml(name) +
      '">' +
      escapeHtml(f.label) +
      (f.is_required ? " *" : "") +
      "</label>" +
      '<input class="form-control mq-input" type="' +
      type +
      '" name="' +
      escapeHtml(name) +
      '" id="' +
      escapeHtml(name) +
      '" value="' +
      escapeHtml(val) +
      '" ' +
      req +
      step +
      min +
      max +
      ">" +
      helpHtml +
      "</div>"
    );
  }

  function init(opts) {
    var form = document.getElementById(opts.formId);
    if (!form) return;

    var schemaUrl = form.getAttribute("data-schema-url");
    var autofillUrl = form.getAttribute("data-autofill-url");
    var processOptions = readJson("mq-process-options", []);
    var existingBlocks = readJson("mq-existing-blocks", []);
    var preferredMaterialId = readJson("mq-preferred-material", null);
    var blocksEl = document.getElementById("mq-process-blocks");
    var blockCountInput = document.getElementById("id_block_count");
    var addBtn = document.getElementById("mq-add-process-block");

    var blockIndex = 0;
    var schemas = {}; // blockIdx -> schema

    function prefix(bi) {
      return "block-" + bi + "-";
    }

    function processOptionsHtml(selectedId) {
      var html = '<option value="">Select a process…</option>';
      processOptions.forEach(function (p) {
        html +=
          '<option value="' +
          p.id +
          '"' +
          (String(selectedId) === String(p.id) ? " selected" : "") +
          ">" +
          escapeHtml(p.label) +
          "</option>";
      });
      return html;
    }

    function updateBlockCount() {
      var n = blocksEl.querySelectorAll(".mq-process-block").length;
      // Recount indices are already on data-block-index; block_count is max index + 1
      var max = -1;
      blocksEl.querySelectorAll(".mq-process-block").forEach(function (b) {
        var i = parseInt(b.getAttribute("data-block-index"), 10);
        if (i > max) max = i;
      });
      blockCountInput.value = String(max + 1);
      void n;
    }

    function addProcessBlock(initial) {
      initial = initial || null;
      var bi = blockIndex++;
      var pfx = prefix(bi);
      var card = document.createElement("div");
      card.className = "mq-wizard-process-card mq-process-block";
      card.setAttribute("data-block-index", String(bi));
      card.innerHTML =
        '<div class="d-flex justify-content-between align-items-center mb-2">' +
        '<h3 class="mq-wizard-section-title mb-0">Process</h3>' +
        '<button type="button" class="btn btn-sm btn-outline-danger mq-remove-block">Remove</button>' +
        "</div>" +
        '<input type="hidden" name="' +
        pfx +
        'qp_id" class="mq-qp-id" value="' +
        escapeHtml(initial && initial.qp_id ? initial.qp_id : "") +
        '">' +
        '<input type="hidden" name="' +
        pfx +
        'sub_count" class="mq-sub-count" value="0">' +
        '<div class="row g-3">' +
        '<div class="col-md-6">' +
        '<label class="form-label">Process</label>' +
        '<select class="form-select mq-process-select" name="' +
        pfx +
        'process_id">' +
        processOptionsHtml(initial && initial.process ? initial.process.id : "") +
        "</select></div>" +
        '<div class="col-md-6 d-none mq-material-wrap">' +
        '<label class="form-label">Material</label>' +
        '<select class="form-select mq-material-select" name="' +
        pfx +
        'material_id">' +
        '<option value="">Select material…</option></select></div>' +
        '<div class="col-md-6 d-none mq-machine-wrap">' +
        '<label class="form-label">Machine</label>' +
        '<select class="form-select mq-machine-select" name="' +
        pfx +
        'machine_id">' +
        '<option value="">Select machine…</option></select></div>' +
        '<div class="col-md-6 d-none mq-labor-wrap">' +
        '<label class="form-label">Labor role</label>' +
        '<select class="form-select mq-labor-select" name="' +
        pfx +
        'labor_id">' +
        '<option value="">Select labor role…</option></select></div></div>' +
        '<div class="row g-3 mt-1 mq-process-fields"></div>' +
        '<div class="mt-3 d-none mq-subprocess-section">' +
        '<h3 class="mq-wizard-section-title mb-2">Sub processes</h3>' +
        '<div class="mq-subprocess-rows"></div>' +
        '<div class="mq-block-add-row">' +
        '<button type="button" class="btn mq-btn-theme mq-master-add btn-sm mq-add-sub">Add Sub Process</button>' +
        "</div></div>";

      blocksEl.appendChild(card);
      updateBlockCount();

      var processSelect = card.querySelector(".mq-process-select");
      var materialWrap = card.querySelector(".mq-material-wrap");
      var materialSelect = card.querySelector(".mq-material-select");
      var machineWrap = card.querySelector(".mq-machine-wrap");
      var machineSelect = card.querySelector(".mq-machine-select");
      var laborWrap = card.querySelector(".mq-labor-wrap");
      var laborSelect = card.querySelector(".mq-labor-select");
      var fieldsEl = card.querySelector(".mq-process-fields");
      var subSection = card.querySelector(".mq-subprocess-section");
      var subRows = card.querySelector(".mq-subprocess-rows");
      var subCountInput = card.querySelector(".mq-sub-count");
      var addSubBtn = card.querySelector(".mq-add-sub");

      function clearBlockBody() {
        schemas[bi] = null;
        fieldsEl.innerHTML = "";
        materialWrap.classList.add("d-none");
        materialSelect.innerHTML = '<option value="">Select material…</option>';
        machineWrap.classList.add("d-none");
        machineSelect.innerHTML = '<option value="">Select machine…</option>';
        laborWrap.classList.add("d-none");
        laborSelect.innerHTML = '<option value="">Select labor role…</option>';
        subSection.classList.add("d-none");
        subRows.innerHTML = "";
        subCountInput.value = "0";
      }

      function renderCatalogSelect(wrap, select, enabled, items, selectedId, emptyLabel) {
        if (!enabled) {
          wrap.classList.add("d-none");
          select.innerHTML = '<option value="">' + emptyLabel + "</option>";
          return;
        }
        wrap.classList.remove("d-none");
        var pick = selectedId || "";
        var html = '<option value="">' + emptyLabel + "</option>";
        (items || []).forEach(function (m) {
          html +=
            '<option value="' +
            m.id +
            '"' +
            (String(pick) === String(m.id) ? " selected" : "") +
            ">" +
            escapeHtml(m.label) +
            "</option>";
        });
        select.innerHTML = html;
      }

      function renderMaterials(schema, selectedId) {
        var pick = selectedId || preferredMaterialId || "";
        renderCatalogSelect(
          materialWrap,
          materialSelect,
          schema.process.use_material_properties,
          schema.materials,
          pick,
          "Select material…"
        );
        if (schema.process.use_material_properties && pick && !selectedId) {
          applyAutofill();
        }
      }

      function renderMachines(schema, selectedId) {
        renderCatalogSelect(
          machineWrap,
          machineSelect,
          schema.process.use_machine_properties,
          schema.machines,
          selectedId || "",
          "Select machine…"
        );
      }

      function renderLabor(schema, selectedId) {
        renderCatalogSelect(
          laborWrap,
          laborSelect,
          schema.process.use_labor_properties,
          schema.labor_roles,
          selectedId || "",
          "Select labor role…"
        );
      }

      function renderProcessFields(schema, values) {
        values = values || {};
        fieldsEl.innerHTML = "";
        (schema.fields || []).forEach(function (f) {
          fieldsEl.insertAdjacentHTML(
            "beforeend",
            fieldInputHtml(f, pfx + "fld_" + f.code, values[f.code])
          );
        });
      }

      function subOptionsHtml(schema, selectedId, usedIds) {
        usedIds = usedIds || [];
        var html = '<option value="">Select sub process…</option>';
        (schema.subprocesses || []).forEach(function (sp) {
          var used =
            usedIds.indexOf(String(sp.id)) >= 0 && String(selectedId) !== String(sp.id);
          if (used) return;
          html +=
            '<option value="' +
            sp.id +
            '"' +
            (String(selectedId) === String(sp.id) ? " selected" : "") +
            ">" +
            escapeHtml(sp.code + " — " + sp.name) +
            "</option>";
        });
        return html;
      }

      function usedSubIds(exceptRow) {
        var ids = [];
        subRows.querySelectorAll(".mq-sub-row").forEach(function (row) {
          if (exceptRow && row === exceptRow) return;
          var sel = row.querySelector(".mq-sub-select");
          if (sel && sel.value) ids.push(String(sel.value));
        });
        return ids;
      }

      function refreshAllSubOptions() {
        var schema = schemas[bi];
        if (!schema) return;
        subRows.querySelectorAll(".mq-sub-row").forEach(function (row) {
          var sel = row.querySelector(".mq-sub-select");
          var cur = sel.value;
          sel.innerHTML = subOptionsHtml(schema, cur, usedSubIds(row));
          sel.value = cur;
        });
      }

      function addSubRow(selectedId, values) {
        var schema = schemas[bi];
        if (!schema || !(schema.subprocesses || []).length) return;

        var si = parseInt(subCountInput.value, 10) || 0;
        subCountInput.value = String(si + 1);
        var spfx = pfx + "sub-" + si + "-";

        var row = document.createElement("div");
        row.className = "mq-wizard-process-card mq-sub-row";
        row.setAttribute("data-sub-index", String(si));
        row.innerHTML =
          '<div class="d-flex justify-content-between align-items-center gap-2 mb-2">' +
          '<div class="flex-grow-1">' +
          '<label class="form-label">Sub process</label>' +
          '<select class="form-select mq-sub-select" name="' +
          spfx +
          'id">' +
          subOptionsHtml(schema, selectedId || "", usedSubIds(null)) +
          "</select></div>" +
          '<button type="button" class="btn btn-sm btn-outline-danger mq-remove-sub mt-4">Remove</button>' +
          "</div>" +
          '<div class="row g-3 mq-sub-fields"></div>';

        subRows.appendChild(row);
        subSection.classList.remove("d-none");

        var select = row.querySelector(".mq-sub-select");
        var fieldsWrap = row.querySelector(".mq-sub-fields");

        function renderSubFields(spId, vals) {
          fieldsWrap.innerHTML = "";
          if (!spId) return;
          var sp = (schema.subprocesses || []).find(function (s) {
            return String(s.id) === String(spId);
          });
          if (!sp) return;
          vals = vals || {};
          (sp.fields || []).forEach(function (f) {
            fieldsWrap.insertAdjacentHTML(
              "beforeend",
              fieldInputHtml(f, spfx + "fld_" + f.code, vals[f.code])
            );
          });
        }

        select.addEventListener("change", function () {
          refreshAllSubOptions();
          renderSubFields(select.value, {});
        });

        row.querySelector(".mq-remove-sub").addEventListener("click", function () {
          row.remove();
          refreshAllSubOptions();
          if (!subRows.querySelector(".mq-sub-row")) {
            // keep section visible so user can add again
          }
        });

        if (selectedId) {
          select.value = String(selectedId);
          renderSubFields(selectedId, values || {});
        }
        refreshAllSubOptions();
      }

      function applySchema(schema, options) {
        options = options || {};
        schemas[bi] = schema;
        renderMaterials(schema, options.material_id);
        renderMachines(schema, options.machine_id);
        renderLabor(schema, options.labor_id);
        renderProcessFields(schema, options.values || {});
        subRows.innerHTML = "";
        subCountInput.value = "0";
        if ((schema.subprocesses || []).length) {
          subSection.classList.remove("d-none");
          var selected = options.selected_subprocess_ids || [];
          var subVals = options.subprocess_values || {};
          if (selected.length) {
            selected.forEach(function (sid) {
              addSubRow(sid, subVals[String(sid)] || {});
            });
          }
        } else {
          subSection.classList.add("d-none");
        }
      }

      function loadSchema(processId, options) {
        if (!processId) {
          clearBlockBody();
          return;
        }
        fetch(schemaUrl + "?process_id=" + encodeURIComponent(processId), {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            if (data.error) throw new Error(data.error);
            applySchema(data, options || {});
          })
          .catch(function (err) {
            clearBlockBody();
            alert(err.message || "Could not load process.");
          });
      }

      function applyAutofill() {
        var schema = schemas[bi];
        if (!schema) return;
        var params = ["process_id=" + encodeURIComponent(schema.process.id)];
        if (materialSelect.value) {
          params.push("material_id=" + encodeURIComponent(materialSelect.value));
        }
        if (machineSelect.value) {
          params.push("machine_id=" + encodeURIComponent(machineSelect.value));
        }
        if (laborSelect.value) {
          params.push("labor_id=" + encodeURIComponent(laborSelect.value));
        }
        if (params.length < 2) return;
        var url = autofillUrl + "?" + params.join("&");
        fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            var pf = data.process_fields || {};
            Object.keys(pf).forEach(function (code) {
              var input = card.querySelector('[name="' + pfx + "fld_" + code + '"]');
              if (!input) return;
              if (input.type === "checkbox") input.checked = pf[code] === "1";
              else if (!input.value) input.value = pf[code];
            });
            var sf = data.subprocess_fields || {};
            subRows.querySelectorAll(".mq-sub-row").forEach(function (row) {
              var sel = row.querySelector(".mq-sub-select");
              if (!sel || !sel.value) return;
              var map = sf[String(sel.value)] || {};
              var si = row.getAttribute("data-sub-index");
              Object.keys(map).forEach(function (code) {
                var input = row.querySelector(
                  '[name="' + pfx + "sub-" + si + "-fld_" + code + '"]'
                );
                if (!input) return;
                if (input.type === "checkbox") input.checked = map[code] === "1";
                else if (!input.value) input.value = map[code];
              });
            });
          })
          .catch(function () {});
      }

      processSelect.addEventListener("change", function () {
        card.querySelector(".mq-qp-id").value = "";
        loadSchema(processSelect.value, {});
      });
      materialSelect.addEventListener("change", applyAutofill);
      machineSelect.addEventListener("change", applyAutofill);
      laborSelect.addEventListener("change", applyAutofill);
      addSubBtn.addEventListener("click", function () {
        if (!schemas[bi]) {
          alert("Select a process first.");
          return;
        }
        if (!(schemas[bi].subprocesses || []).length) {
          alert("This process has no linked sub processes.");
          return;
        }
        addSubRow("", {});
      });
      card.querySelector(".mq-remove-block").addEventListener("click", function () {
        card.remove();
        delete schemas[bi];
        updateBlockCount();
        if (!blocksEl.querySelector(".mq-process-block")) {
          addProcessBlock(null);
        }
      });

      if (initial && initial.process) {
        applySchema(initial, {
          material_id: initial.material_id,
          machine_id: initial.machine_id,
          labor_id: initial.labor_id,
          values: initial.values,
          selected_subprocess_ids: initial.selected_subprocess_ids,
          subprocess_values: initial.subprocess_values,
        });
      }
    }

    addBtn.addEventListener("click", function () {
      addProcessBlock(null);
    });

    form.addEventListener("submit", function (ev) {
      var submitter = ev.submitter;
      var action = submitter && submitter.name === "wizard_action" ? submitter.value : "";
      if (action === "back") {
        form.querySelectorAll("[required]").forEach(function (n) {
          n.removeAttribute("required");
        });
      }
      updateBlockCount();
    });

    if (existingBlocks && existingBlocks.length) {
      existingBlocks.forEach(function (b) {
        addProcessBlock(b);
      });
    } else {
      addProcessBlock(null);
    }
  }

  global.MQWizardProcesses = { init: init };
})(window);
