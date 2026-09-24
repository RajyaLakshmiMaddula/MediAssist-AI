/* =========================================================================
   MediAssist AI — client behaviour
   Two jobs: the typing demo on the landing page, and the live preview on the
   dashboard that calls /api/analyze without saving a consultation.
   ========================================================================= */

(function () {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------------
     Landing page: type out example complaints
     --------------------------------------------------------------------- */
  const demo = document.getElementById("demo-input");
  if (demo) {
    const lines = [
      "High fever for three days with severe headache and pain behind my eyes.",
      "Continuous sneezing with itchy watery eyes, but no fever at all.",
      "Burning while passing urine since yesterday and going very often.",
      "Dry cough for two weeks and I have lost my sense of smell."
    ];

    if (reduceMotion) {
      demo.value = lines[0];
    } else {
      let line = 0, char = 0, erasing = false;

      const tick = () => {
        const text = lines[line];
        if (!erasing) {
          demo.value = text.slice(0, ++char);
          if (char === text.length) {
            erasing = true;
            return setTimeout(tick, 2200);
          }
          return setTimeout(tick, 32);
        }
        demo.value = text.slice(0, --char);
        if (char === 0) {
          erasing = false;
          line = (line + 1) % lines.length;
          return setTimeout(tick, 400);
        }
        setTimeout(tick, 12);
      };
      setTimeout(tick, 900);
    }
  }

  /* ---------------------------------------------------------------------
     Dashboard: fill the textarea from an example chip
     --------------------------------------------------------------------- */
  const symptomBox = document.getElementById("symptoms");

  document.querySelectorAll("[data-example]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!symptomBox) return;
      symptomBox.value = button.dataset.example;
      symptomBox.focus();
      symptomBox.dispatchEvent(new Event("input"));
    });
  });

  /* ---------------------------------------------------------------------
     Dashboard: live preview
     --------------------------------------------------------------------- */
  const previewBtn = document.getElementById("preview-btn");
  const panel = document.getElementById("live-panel");
  const panelBody = document.getElementById("live-body");
  const spinner = document.getElementById("live-spinner");

  const csrfToken = () => {
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : "";
  };

  const escapeHtml = (value) =>
    String(value).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));

  const chips = (items, className) =>
    items.length
      ? `<ul class="chips">${items
          .map((i) => `<li class="chip ${className}">${escapeHtml(i)}</li>`)
          .join("")}</ul>`
      : '<p style="color:var(--muted);font-size:.9rem;margin:0">None detected.</p>';

  const render = (data) => {
    if (data.status === "emergency") {
      panelBody.innerHTML = `
        <div class="banner banner-emergency">
          <p><strong>Warning sign detected.</strong>
          ${escapeHtml(data.red_flags[0].message)}
          Submit the form only if you understand this needs immediate in-person care.</p>
        </div>`;
      return;
    }

    if (data.status === "no_symptoms") {
      panelBody.innerHTML = `
        <div class="banner banner-caution">
          <p><strong>Nothing recognised yet.</strong>
          Name what you feel and where, for example "burning pain in my upper stomach
          after meals".</p>
        </div>`;
      return;
    }

    const rows = data.candidates.length
      ? `<ul class="diff">${data.candidates
          .map(
            (c) => `
            <li>
              <div>
                <div>${escapeHtml(c.name)}</div>
                <div class="diff-dept">${escapeHtml(c.department)}</div>
              </div>
              <div class="diff-bar"><span style="width:${c.confidence}%"></span></div>
              <div class="diff-pct">${Math.round(c.confidence)}%</div>
            </li>`
          )
          .join("")}</ul>`
      : `<div class="banner banner-caution"><p>Symptoms were understood, but nothing in
         the knowledge base matched closely enough to report.</p></div>`;

    panelBody.innerHTML = `
      <h3 style="font-size:.95rem;margin-bottom:.5rem">Symptoms found</h3>
      ${chips(data.symptoms, "")}
      ${data.denied.length
        ? `<h3 style="font-size:.95rem;margin:1rem 0 .5rem">Ruled out</h3>${chips(data.denied, "chip-denied")}`
        : ""}
      <h3 style="font-size:.95rem;margin:1.1rem 0 .5rem">Possible conditions</h3>
      ${rows}
      <p style="font-size:.84rem;color:var(--muted);margin:.9rem 0 0">
        Severity read as <strong>${escapeHtml(data.severity)}</strong> ·
        duration ${escapeHtml(data.duration)} ·
        processed with ${escapeHtml(data.engine)}.
        Submit the form to save this and get the full care plan.
      </p>`;
  };

  if (previewBtn) {
    previewBtn.addEventListener("click", async () => {
      const text = symptomBox ? symptomBox.value.trim() : "";
      if (text.length < 8) {
        symptomBox.focus();
        panel.hidden = false;
        panelBody.innerHTML = `
          <div class="banner banner-caution">
            <p>Write a little more first — a few words about what you feel and when it started.</p>
          </div>`;
        return;
      }

      panel.hidden = false;
      spinner.hidden = false;
      previewBtn.disabled = true;
      panelBody.innerHTML = '<p style="color:var(--muted);margin:0">Reading your description…</p>';

      try {
        const response = await fetch("/api/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken()
          },
          body: JSON.stringify({
            symptoms: text,
            age: document.getElementById("age") ? document.getElementById("age").value : null,
            gender: document.getElementById("gender") ? document.getElementById("gender").value : null,
            severity: document.getElementById("severity") ? document.getElementById("severity").value : null,
            duration: document.getElementById("duration") ? document.getElementById("duration").value : null
          })
        });

        const data = await response.json();
        if (!response.ok) {
          panelBody.innerHTML = `<div class="banner banner-caution"><p>${escapeHtml(
            data.message || "The preview could not be generated."
          )}</p></div>`;
        } else {
          render(data);
        }
      } catch (err) {
        panelBody.innerHTML = `
          <div class="banner banner-caution">
            <p>The preview could not reach the server. Submit the form instead.</p>
          </div>`;
      } finally {
        spinner.hidden = true;
        previewBtn.disabled = false;
      }
    });
  }

  /* ---------------------------------------------------------------------
     Textarea auto-grow
     --------------------------------------------------------------------- */
  if (symptomBox) {
    const grow = () => {
      symptomBox.style.height = "auto";
      symptomBox.style.height = Math.max(130, symptomBox.scrollHeight) + "px";
    };
    symptomBox.addEventListener("input", grow);
  }
})();
