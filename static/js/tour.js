(function () {
  if (!window.MQ || !MQ.isAuthenticated || typeof Shepherd === "undefined") return;

  function post(url, data) {
    const body = new URLSearchParams(data || {});
    return fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": MQ.csrfToken,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });
  }

  function buildTour() {
    const tour = new Shepherd.Tour({
      useModalOverlay: true,
      defaultStepOptions: {
        cancelIcon: { enabled: true },
        classes: "shadow-md",
        scrollTo: { behavior: "smooth", block: "center" },
      },
    });

    const steps = [
      {
        id: "welcome",
        text: "Welcome to Manufacturing Quote. This short tour shows where to click for the full Excel → cost → PDF flow.",
        attachTo: { element: '[data-tour="nav-dashboard"]', on: "right" },
      },
      {
        id: "imports",
        text: "Download Excel templates here, fill them offline, then upload to import masters.",
        attachTo: { element: '[data-tour="nav-imports"]', on: "right" },
      },
      {
        id: "catalog",
        text: "Imported materials, machines, and labor roles appear in Catalog.",
        attachTo: { element: '[data-tour="nav-catalog"]', on: "right" },
      },
    ];

    if (MQ.isAdmin) {
      steps.push({
        id: "custom-fields",
        text: "Add extra Excel columns without code changes via Custom Fields.",
        attachTo: { element: '[data-tour="nav-custom-fields"]', on: "right" },
      });
    }

    steps.push(
      {
        id: "templates",
        text: "Define formulas, BOM, and machine time on Product Templates.",
        attachTo: { element: '[data-tour="nav-templates"]', on: "right" },
      },
      {
        id: "quotes",
        text: "Create a quote, calculate costs, and download the customer PDF.",
        attachTo: { element: '[data-tour="nav-quotes"]', on: "right" },
      }
    );

    if (MQ.isAdmin) {
      steps.push({
        id: "error-logs",
        text: "All errors and exceptions are stored in the database here — search by correlation id from flash messages.",
        attachTo: { element: '[data-tour="nav-error-logs"]', on: "right" },
      });
    }

    steps.forEach(function (step, index) {
      const buttons = [];
      if (index > 0) {
        buttons.push({ text: "Back", action: tour.back, classes: "btn btn-sm btn-outline-secondary" });
      }
      buttons.push({
        text: "Skip",
        action: function () {
          post(MQ.tourDismissUrl);
          tour.cancel();
        },
        classes: "btn btn-sm btn-link",
      });
      if (index < steps.length - 1) {
        buttons.push({ text: "Next", action: tour.next, classes: "btn btn-sm btn-primary" });
      } else {
        buttons.push({
          text: "Finish",
          action: function () {
            post(MQ.tourCompleteUrl);
            tour.complete();
          },
          classes: "btn btn-sm btn-primary",
        });
      }
      tour.addStep({
        id: step.id,
        text: step.text,
        attachTo: step.attachTo,
        buttons: buttons,
      });
    });

    tour.on("cancel", function () {
      post(MQ.tourDismissUrl);
    });
    tour.on("show", function (e) {
      const idx = tour.steps.indexOf(e.step);
      if (idx >= 0) post(MQ.tourStepUrl, { step: idx });
    });

    return tour;
  }

  fetch(MQ.tourStatusUrl)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.should_start) {
        const tour = buildTour();
        tour.start();
      }
    })
    .catch(function () {});

  // Restart link triggers redirect then auto-start via should_start
})();
