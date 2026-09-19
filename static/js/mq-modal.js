/**
 * App modal helpers — no browser alert/confirm.
 * MQ.confirm(options) -> Promise<boolean>
 * MQ.alert(options) -> Promise<void>
 * Also supports [data-mq-confirm-submit] on buttons inside forms.
 */
(function () {
  window.MQ = window.MQ || {};

  var root = null;
  var titleEl = null;
  var messageEl = null;
  var iconEl = null;
  var confirmBtn = null;
  var cancelBtn = null;
  var closeBtn = null;
  var resolveFn = null;
  var mode = "confirm";

  function ensureDom() {
    root = document.getElementById("mq-modal");
    if (!root) return false;
    titleEl = document.getElementById("mq-modal-title");
    messageEl = document.getElementById("mq-modal-message");
    iconEl = document.getElementById("mq-modal-icon");
    confirmBtn = document.getElementById("mq-modal-confirm");
    cancelBtn = document.getElementById("mq-modal-cancel");
    closeBtn = document.getElementById("mq-modal-close");
    return true;
  }

  function setVariant(variant) {
    root.classList.remove("is-danger", "is-warning", "is-info", "is-success");
    root.classList.add("is-" + (variant || "info"));
    var icons = {
      danger:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
      warning:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16h.01"/></svg>',
      success:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-5"/></svg>',
      info:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01"/><path d="M11 12h1v5h1"/></svg>',
    };
    if (iconEl) iconEl.innerHTML = icons[variant] || icons.info;
  }

  function openModal(opts) {
    if (!ensureDom()) return Promise.resolve(mode === "confirm" ? false : undefined);
    opts = opts || {};
    mode = opts.mode || "confirm";
    setVariant(opts.variant || (mode === "confirm" ? "warning" : "info"));
    titleEl.textContent = opts.title || (mode === "confirm" ? "Confirm" : "Notice");
    messageEl.textContent = opts.message || "";
    confirmBtn.textContent = opts.confirmLabel || (mode === "confirm" ? "Confirm" : "OK");
    cancelBtn.textContent = opts.cancelLabel || "Cancel";
    cancelBtn.hidden = mode === "alert";
    confirmBtn.classList.toggle("mq-modal-btn-danger", opts.variant === "danger");
    root.hidden = false;
    root.classList.add("is-open");
    document.body.classList.add("mq-modal-open");
    confirmBtn.focus();

    return new Promise(function (resolve) {
      resolveFn = resolve;
    });
  }

  function closeModal(result) {
    if (!root) return;
    root.classList.remove("is-open");
    root.hidden = true;
    document.body.classList.remove("mq-modal-open");
    var fn = resolveFn;
    resolveFn = null;
    if (fn) fn(result);
  }

  MQ.confirm = function (opts) {
    opts = opts || {};
    opts.mode = "confirm";
    opts.variant = opts.variant || "danger";
    return openModal(opts);
  };

  MQ.alert = function (opts) {
    opts = opts || {};
    opts.mode = "alert";
    opts.variant = opts.variant || "info";
    opts.confirmLabel = opts.confirmLabel || "OK";
    return openModal(opts).then(function () {});
  };

  function bindOnce() {
    if (!ensureDom() || root.dataset.bound === "1") return;
    root.dataset.bound = "1";

    confirmBtn.addEventListener("click", function () {
      closeModal(mode === "confirm" ? true : undefined);
    });
    cancelBtn.addEventListener("click", function () {
      closeModal(false);
    });
    closeBtn.addEventListener("click", function () {
      closeModal(mode === "confirm" ? false : undefined);
    });
    root.addEventListener("click", function (e) {
      if (e.target === root || e.target.classList.contains("mq-modal-backdrop")) {
        closeModal(mode === "confirm" ? false : undefined);
      }
    });
    document.addEventListener("keydown", function (e) {
      if (!root.classList.contains("is-open")) return;
      if (e.key === "Escape") {
        e.preventDefault();
        closeModal(mode === "confirm" ? false : undefined);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", bindOnce);
  if (document.readyState !== "loading") bindOnce();

  // Declarative confirm-before-submit (works after HTMX swaps)
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-mq-confirm-submit]");
    if (!btn) return;
    var form = btn.closest("form");
    if (!form) return;
    e.preventDefault();
    MQ.confirm({
      title: btn.getAttribute("data-mq-title") || "Are you sure?",
      message: btn.getAttribute("data-mq-message") || "",
      confirmLabel: btn.getAttribute("data-mq-confirm-label") || "Confirm",
      cancelLabel: btn.getAttribute("data-mq-cancel-label") || "Cancel",
      variant: btn.getAttribute("data-mq-variant") || "danger",
    }).then(function (ok) {
      if (ok) form.submit();
    });
  });

  function mapFlashVariant(level) {
    var tag = (level || "info").toLowerCase();
    if (tag.indexOf("error") !== -1 || tag.indexOf("danger") !== -1) return "danger";
    if (tag.indexOf("success") !== -1) return "success";
    if (tag.indexOf("warning") !== -1) return "warning";
    return "info";
  }

  function flashTitle(variant) {
    if (variant === "success") return "Success";
    if (variant === "danger") return "Error";
    if (variant === "warning") return "Warning";
    return "Notice";
  }

  MQ.showFlashMessages = function () {
    var el = document.getElementById("mq-django-messages");
    if (!el || !el.textContent.trim()) return Promise.resolve();
    var items;
    try {
      items = JSON.parse(el.textContent);
    } catch (err) {
      return Promise.resolve();
    }
    if (!items || !items.length) return Promise.resolve();

    return items.reduce(function (chain, item) {
      return chain.then(function () {
        var variant = mapFlashVariant(item.level);
        return MQ.alert({
          title: flashTitle(variant),
          message: item.text || "",
          variant: variant,
          confirmLabel: "OK",
        });
      });
    }, Promise.resolve());
  };
})();
