/* Tessera dashboard.
 *
 * Plain JavaScript, no build step and no third-party requests. Every piece of text from the
 * API is inserted with textContent / createTextNode, never innerHTML.
 */
"use strict";

(function () {
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var root = document.documentElement;

  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  var nf = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  var nf1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

  /** Tiny element builder: h("div", {class: "x", onclick: fn}, child, child...). */
  function h(tag, props) {
    var el = document.createElement(tag);
    var attrs = props || {};
    Object.keys(attrs).forEach(function (key) {
      var value = attrs[key];
      if (value === null || value === undefined || value === false) return;
      if (key === "class") el.className = value;
      else if (key === "style") {
        Object.keys(value).forEach(function (name) {
          el.style.setProperty(name, value[name]);
        });
      } else if (key.slice(0, 2) === "on") el.addEventListener(key.slice(2), value);
      else el.setAttribute(key, value === true ? "" : value);
    });
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }

  function append(el, child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) child.forEach(function (c) { append(el, c); });
    else el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }

  function plural(count, one, many) {
    return count === 1 ? one : many;
  }

  function billTotal(p) {
    var b = p.bill || {};
    return (b.consultation || 0) + (b.medicine || 0) + (b.lab || 0);
  }

  function isAdmitted(p) {
    return String(p.status).toLowerCase() === "admitted";
  }

  /* ----------------------------------------------------------------- API */

  function ApiError(message, status) {
    this.message = message;
    this.status = status;
  }

  function api(path, params, signal) {
    var url = new URL(path, window.location.origin);
    Object.keys(params || {}).forEach(function (key) {
      var value = params[key];
      if (value !== "" && value !== null && value !== undefined) url.searchParams.set(key, value);
    });
    return fetch(url, { signal: signal, headers: { Accept: "application/json" } }).then(
      function (res) {
        return res
          .json()
          .catch(function () { return null; })
          .then(function (body) {
            if (!res.ok) {
              var message = body && body.message ? body.message : "Request failed (" + res.status + ").";
              throw new ApiError(message, res.status);
            }
            return body;
          });
      },
      function (err) {
        if (err && err.name === "AbortError") throw err;
        throw new ApiError("Can't reach the patient service.", 0);
      }
    );
  }

  /* --------------------------------------------------------------- state */

  var state = { q: "", department: "", status: "", sort: "id", order: "asc", offset: 0, limit: 10 };
  var known = { patients: new Map(), highestId: null, longestId: null };
  var directoryRequest = null;

  /* -------------------------------------------------------------- banner */

  function friendly(error) {
    if (error.status === 0) return "Can't reach the patient service. Check that it's running, then try again.";
    if (error.status === 503) return "The service isn't configured. " + error.message;
    if (error.status === 502) return "The patient data source didn't respond. " + error.message;
    return error.message;
  }

  function showBanner(error, retry) {
    var banner = $("#banner");
    banner.replaceChildren(
      h("span", {}, friendly(error)),
      h("button", { class: "btn", type: "button", onclick: retry }, "Try again")
    );
    banner.hidden = false;
  }

  function hideBanner() {
    $("#banner").hidden = true;
  }

  /* ---------------------------------------------------------------- tooltip */

  var tip = $("#tip");

  function showTip(el, patient) {
    tip.replaceChildren(
      h("strong", {}, patient.name),
      patient.status + ", " + nf.format(patient.daysAdmitted || 0) + " " +
        plural(patient.daysAdmitted, "day", "days")
    );
    tip.hidden = false;
    var rect = el.getBoundingClientRect();
    var left = rect.left + rect.width / 2 - tip.offsetWidth / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tip.offsetWidth - 8));
    var top = rect.top - tip.offsetHeight - 10;
    if (top < 8) top = rect.bottom + 10;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  function hideTip() {
    tip.hidden = true;
  }

  /* --------------------------------------------------------------- census */

  function describe(p) {
    var parts = [
      p.name,
      p.department,
      String(p.status).toLowerCase(),
      nf.format(p.daysAdmitted || 0) + " " + plural(p.daysAdmitted, "day", "days"),
    ];
    if (p.id === known.highestId) parts.push("highest bill on record");
    if (p.id === known.longestId) parts.push("longest stay on record");
    return parts.join(", ");
  }

  function makeCell(p, index) {
    var classes = ["cell", isAdmitted(p) ? "cell--admitted" : "cell--discharged"];
    if (p.id === known.highestId) classes.push("cell--bill");
    if (p.id === known.longestId) classes.push("cell--stay");
    var el = h("button", {
      type: "button",
      class: classes.join(" "),
      style: { "--i": String(Math.min(index, 80)) },
      "aria-label": describe(p),
    });
    el.addEventListener("click", function () { openDrawer(p, el); });
    el.addEventListener("pointerenter", function () { showTip(el, p); });
    el.addEventListener("pointerleave", hideTip);
    el.addEventListener("focus", function () { showTip(el, p); });
    el.addEventListener("blur", hideTip);
    return el;
  }

  function renderCensus(patients, departments) {
    var groups = new Map();
    departments.forEach(function (d) { groups.set(d.department, []); });
    patients.forEach(function (p) {
      var key = (p.department || "").trim() || "Unassigned";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(p);
    });

    var index = 0;
    var frag = document.createDocumentFragment();
    groups.forEach(function (list, name) {
      if (!list.length) return;
      frag.append(
        h("section", { class: "ward", style: { "--cols": String(Math.min(list.length, list.length > 24 ? 10 : 5)) } },
          h("div", { class: "ward-name" },
            h("span", {}, name),
            h("span", { class: "ward-count" }, String(list.length))),
          h("div", { class: "ward-cells", role: "group",
                     "aria-label": name + ", " + list.length + " " + plural(list.length, "patient", "patients") },
            list.map(function (p) { return makeCell(p, index++); })))
      );
    });
    $("#census").replaceChildren(frag);
  }

  /* ----------------------------------------------------------- hero + notes */

  function renderHero(summary, total) {
    var headline = $("#headline");
    var subline = $("#subline");
    if (!total) {
      headline.textContent = "No patient records yet.";
      subline.textContent = "Records will appear here as soon as the data source has some.";
      return;
    }
    var admitted = summary.admittedCount;
    headline.textContent =
      nf.format(admitted) + " of " + nf.format(total) + " " + plural(total, "patient", "patients") +
      " " + plural(admitted, "is", "are") + " admitted.";
    subline.textContent =
      nf.format(summary.dischargedCount) + " discharged. Average age " + nf1.format(summary.averageAge) + ".";
  }

  function fillRecord(button, value, detail, id) {
    $("[data-slot=value]", button).textContent = value;
    $("[data-slot=detail]", button).textContent = detail;
    button.disabled = false;
    button.onclick = function () { openById(id, button); };
  }

  function renderRecords(highest, longest) {
    if (highest) {
      fillRecord($("#note-bill"), nf.format(highest.totalBill),
        highest.name + ", " + highest.department, highest.id);
    } else {
      $("#note-bill [data-slot=value]").textContent = "Not available";
    }
    if (longest) {
      fillRecord($("#note-stay"),
        nf.format(longest.daysAdmitted) + " " + plural(longest.daysAdmitted, "day", "days"),
        longest.name + ", " + longest.department, longest.id);
    } else {
      $("#note-stay [data-slot=value]").textContent = "Not available";
    }
  }

  /* ---------------------------------------------------------------- ledger */

  function renderLedger(departments) {
    var ledger = $("#ledger");
    var max = Math.max.apply(null, departments.map(function (d) { return d.patientCount; }).concat([1]));
    var head = h("div", { class: "ledger-head", "aria-hidden": "true" },
      h("span", { class: "col-name" }, "Department"),
      h("span", { class: "col-bar" }),
      h("span", { class: "ledger-num col-patients" }, "Patients"),
      h("span", { class: "ledger-num col-admitted" }, "Admitted"),
      h("span", { class: "ledger-num col-stay" }, "Avg stay"),
      h("span", { class: "ledger-num col-billed" }, "Billed"));

    var rows = departments.map(function (d) {
      var pressed = state.department.toLowerCase() === d.department.toLowerCase();
      var row = h("button", {
        type: "button",
        class: "ledger-row",
        "data-department": d.department,
        "aria-pressed": pressed ? "true" : "false",
        "aria-label": d.department + ": " + d.patientCount + " " + plural(d.patientCount, "patient", "patients") +
          ", " + d.admittedCount + " admitted, average stay " + nf1.format(d.averageStayDays) +
          " days, " + nf.format(d.totalRevenue) + " billed. Filter the directory by this department.",
      },
        h("span", { class: "ledger-name" }, d.department),
        h("span", { class: "ledger-track" },
          h("span", { class: "ledger-fill", style: { width: (d.patientCount / max) * 100 + "%" } })),
        h("span", { class: "ledger-num ledger-patients" }, nf.format(d.patientCount)),
        h("span", { class: "ledger-num ledger-admitted" }, nf.format(d.admittedCount)),
        h("span", { class: "ledger-num ledger-stay" }, nf1.format(d.averageStayDays) + " days"),
        h("span", { class: "ledger-num ledger-billed" }, nf.format(d.totalRevenue)));
      row.addEventListener("click", function () {
        var same = state.department.toLowerCase() === d.department.toLowerCase();
        setDepartment(same ? "" : d.department);
        if (!same) {
          var target = $("#directory");
          target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
          target.focus({ preventScroll: true });
        }
      });
      return row;
    });

    ledger.replaceChildren(head);
    ledger.append.apply(ledger, rows);

    var select = $("#department");
    select.replaceChildren(h("option", { value: "" }, "All departments"));
    departments.forEach(function (d) {
      select.append(h("option", { value: d.department }, d.department));
    });
    select.value = state.department;
  }

  function syncLedgerPressed() {
    Array.prototype.forEach.call(document.querySelectorAll(".ledger-row"), function (row) {
      var on = state.department && row.dataset.department.toLowerCase() === state.department.toLowerCase();
      row.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  /* ------------------------------------------------------------- directory */

  function pill(status) {
    var admitted = String(status).toLowerCase() === "admitted";
    return h("span", { class: "pill " + (admitted ? "pill--admitted" : "pill--discharged") }, status || "Unknown");
  }

  function makeRow(p) {
    var nameButton = h("button", { type: "button", class: "name-btn" }, p.name || "Patient " + p.id);
    var tr = h("tr", {},
      h("td", { class: "id" }, String(p.id)),
      h("td", {}, nameButton),
      h("td", {}, p.department),
      h("td", {}, p.doctor),
      h("td", { class: "num" }, nf.format(p.age || 0)),
      h("td", { class: "num" }, nf.format(p.daysAdmitted || 0)),
      h("td", { class: "num" }, nf.format(billTotal(p))),
      h("td", {}, pill(p.status)));
    tr.addEventListener("click", function () { openDrawer(p, nameButton); });
    return tr;
  }

  function filtersActive() {
    return Boolean(state.q || state.department || state.status);
  }

  function renderDirectory(page) {
    page.items.forEach(function (p) { known.patients.set(p.id, p); });
    state.total = page.total;

    $("#rows").replaceChildren.apply($("#rows"), page.items.map(makeRow));
    var empty = page.total === 0;
    $(".table-wrap").hidden = empty;
    $(".pager").hidden = empty;
    $("#empty").hidden = !empty;

    $("#dir-count").textContent =
      nf.format(page.total) + " " + plural(page.total, "patient", "patients") +
      (filtersActive() ? " match these filters" : " on record");

    if (!empty) {
      var from = page.offset + 1;
      var to = page.offset + page.items.length;
      $("#range").textContent = "Showing " + nf.format(from) + " to " + nf.format(to) + " of " + nf.format(page.total);
      $("#prev").disabled = page.offset <= 0;
      $("#next").disabled = page.offset + page.limit >= page.total;
    }
  }

  function loadDirectory() {
    if (directoryRequest) directoryRequest.abort();
    directoryRequest = new AbortController();
    var thisRequest = directoryRequest;
    var section = $("#directory");
    section.classList.add("is-loading");

    return api("/patients", {
      q: state.q, department: state.department, status: state.status,
      sort: state.sort, order: state.order, limit: state.limit, offset: state.offset,
    }, thisRequest.signal).then(
      function (page) {
        hideBanner();
        renderDirectory(page);
      },
      function (error) {
        if (error && error.name === "AbortError") return;
        showBanner(error, loadDirectory);
      }
    ).then(function () {
      if (directoryRequest === thisRequest) section.classList.remove("is-loading");
    });
  }

  function resetPaging() {
    state.offset = 0;
  }

  function setDepartment(name) {
    state.department = name;
    $("#department").value = name;
    resetPaging();
    syncLedgerPressed();
    loadDirectory();
  }

  function updateSortHeaders() {
    Array.prototype.forEach.call(document.querySelectorAll("th[data-sort]"), function (th) {
      if (th.dataset.sort === state.sort) {
        th.setAttribute("aria-sort", state.order === "asc" ? "ascending" : "descending");
      } else {
        th.removeAttribute("aria-sort");
      }
    });
  }

  function debounce(fn, wait) {
    var timer;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(null, args); }, wait);
    };
  }

  function bindDirectory() {
    $("#filters").addEventListener("submit", function (e) { e.preventDefault(); });

    $("#q").addEventListener("input", debounce(function (e) {
      state.q = e.target.value.trim();
      resetPaging();
      loadDirectory();
    }, 250));

    $("#department").addEventListener("change", function (e) { setDepartment(e.target.value); });

    Array.prototype.forEach.call(document.querySelectorAll("input[name=status]"), function (input) {
      input.addEventListener("change", function () {
        state.status = input.value;
        resetPaging();
        loadDirectory();
      });
    });

    Array.prototype.forEach.call(document.querySelectorAll("th[data-sort] button"), function (button) {
      button.addEventListener("click", function () {
        var field = button.parentElement.dataset.sort;
        if (state.sort === field) state.order = state.order === "asc" ? "desc" : "asc";
        else { state.sort = field; state.order = "asc"; }
        resetPaging();
        updateSortHeaders();
        loadDirectory();
      });
    });

    $("#prev").addEventListener("click", function () {
      state.offset = Math.max(0, state.offset - state.limit);
      loadDirectory();
    });
    $("#next").addEventListener("click", function () {
      state.offset += state.limit;
      loadDirectory();
    });

    $("#clear").addEventListener("click", function () {
      state.q = "";
      state.status = "";
      $("#q").value = "";
      document.querySelector("input[name=status][value='']").checked = true;
      setDepartment("");
    });
  }

  /* ---------------------------------------------------------------- drawer */

  var drawer = $("#drawer");
  var scrim = $("#scrim");
  var lastFocus = null;
  var inertTargets = ["header.top", "main", "footer.foot"];

  function setInert(on) {
    inertTargets.forEach(function (selector) {
      var el = $(selector);
      if (el) el.inert = on;
    });
  }

  function drawerContent(p) {
    var b = p.bill || {};
    var total = billTotal(p);
    var segments = [
      { label: "Consultation", value: b.consultation || 0, color: "var(--seg-1)" },
      { label: "Medicine", value: b.medicine || 0, color: "var(--seg-2)" },
      { label: "Lab", value: b.lab || 0, color: "var(--seg-3)" },
    ];

    var facts = h("dl", { class: "facts" },
      fact("Patient ID", String(p.id)),
      fact("Department", p.department || "Not recorded"),
      fact("Doctor", p.doctor || "Not recorded"),
      fact("Age", nf.format(p.age || 0)),
      fact("Time admitted", nf.format(p.daysAdmitted || 0) + " " + plural(p.daysAdmitted, "day", "days")));

    var sections = [facts];

    var flags = [];
    if (p.id === known.highestId) flags.push(h("li", {}, h("span", { class: "key key-bill", "aria-hidden": "true" }), "Highest bill on record"));
    if (p.id === known.longestId) flags.push(h("li", {}, h("span", { class: "key key-stay", "aria-hidden": "true" }), "Longest stay on record"));
    if (flags.length) sections.push(h("ul", { class: "flags" }, flags));

    var billBody;
    if (total > 0) {
      billBody = [
        h("div", { class: "bill-bar", role: "img",
                   "aria-label": segments.map(function (s) { return s.label + " " + nf.format(s.value); }).join(", ") },
          segments.filter(function (s) { return s.value > 0; }).map(function (s) {
            return h("span", { class: "bill-seg", style: { flex: String(s.value), background: s.color } });
          })),
        h("ul", { class: "bill-list" },
          segments.map(function (s) {
            return h("li", {},
              h("span", { class: "sw", style: { background: s.color }, "aria-hidden": "true" }),
              s.label,
              h("span", { class: "amt" }, nf.format(s.value)));
          }),
          h("li", { class: "bill-total" }, "Total billed", h("span", { class: "amt" }, nf.format(total)))),
      ];
    } else {
      billBody = [h("p", { class: "block-note" }, "No charges recorded for this patient.")];
    }
    sections.push(h("section", { class: "drawer-section" }, h("h3", {}, "Billing"), billBody));
    return sections;
  }

  function fact(label, value) {
    return h("div", {}, h("dt", {}, label), h("dd", {}, value));
  }

  function openDrawer(p, origin) {
    hideTip();
    lastFocus = origin || document.activeElement;
    $("#drawer-title").textContent = p.name || "Patient " + p.id;
    $("#drawer-sub").replaceChildren(pill(p.status));
    $("#drawer-body").replaceChildren.apply($("#drawer-body"), drawerContent(p));

    scrim.hidden = false;
    drawer.hidden = false;
    setInert(true);
    requestAnimationFrame(function () {
      scrim.classList.add("is-open");
      drawer.classList.add("is-open");
    });
    $("#drawer-close").focus();
  }

  function closeDrawer() {
    if (drawer.hidden) return;
    scrim.classList.remove("is-open");
    drawer.classList.remove("is-open");
    setInert(false);
    setTimeout(function () {
      drawer.hidden = true;
      scrim.hidden = true;
    }, reduceMotion ? 0 : 280);
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  }

  function openById(id, origin) {
    var cached = known.patients.get(id);
    if (cached) return openDrawer(cached, origin);
    return api("/patients/" + id).then(
      function (p) { known.patients.set(p.id, p); openDrawer(p, origin); },
      function (error) { showBanner(error, hideBanner); }
    );
  }

  function bindDrawer() {
    $("#drawer-close").addEventListener("click", closeDrawer);
    scrim.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function (e) {
      if (drawer.hidden) return;
      if (e.key === "Escape") { closeDrawer(); return; }
      if (e.key !== "Tab") return;
      var items = drawer.querySelectorAll("button, [href], input, select, [tabindex]:not([tabindex='-1'])");
      if (!items.length) return;
      var first = items[0];
      var last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  /* ----------------------------------------------------------------- theme */

  function currentTheme() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function syncThemeLabel() {
    $("#theme").setAttribute("aria-label",
      currentTheme() === "dark" ? "Switch to the light theme" : "Switch to the dark theme");
  }

  function bindTheme() {
    syncThemeLabel();
    $("#theme").addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("patient-theme", next); } catch (e) { /* storage unavailable */ }
      syncThemeLabel();
    });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeLabel);
  }

  /* -------------------------------------------------------------- start up */

  var SOURCES = {
    file: ["Offline data", "Reading patients from a local file."],
    remote: ["Live service", "Reading patients from the upstream patient service."],
    memory: ["Test data", "Reading patients held in memory."],
  };

  function renderMeta(meta) {
    var source = $("#source");
    var info = SOURCES[meta.source] || [meta.source, ""];
    source.textContent = info[0];
    source.title = info[1];
    source.dataset.source = meta.source;
    source.hidden = false;
    $("#version").textContent = "v" + meta.version;
  }

  function value(result) {
    return result.status === "fulfilled" ? result.value : null;
  }

  function loadOverview() {
    hideBanner();
    return Promise.allSettled([
      api("/meta"),
      api("/patients/admission/summary"),
      api("/patients/highest-bill"),
      api("/patients/longest-stay"),
      api("/analytics/departments"),
      api("/patients", { limit: 200, sort: "id" }),
    ]).then(function (results) {
      var meta = value(results[0]);
      var summary = value(results[1]);
      var highest = value(results[2]);
      var longest = value(results[3]);
      var departments = value(results[4]) || [];
      var everyone = value(results[5]);

      if (meta) renderMeta(meta);

      if (!everyone) {
        var failure = results[5].reason;
        $("#headline").textContent = "Patient records are unavailable.";
        $("#subline").textContent = "";
        showBanner(failure, start);
        return false;
      }

      known.highestId = highest ? highest.id : null;
      known.longestId = longest ? longest.id : null;
      everyone.items.forEach(function (p) { known.patients.set(p.id, p); });

      var admitted = everyone.items.filter(isAdmitted).length;
      var fallback = {
        admittedCount: admitted,
        dischargedCount: everyone.items.length - admitted,
        averageAge: everyone.items.length
          ? everyone.items.reduce(function (sum, p) { return sum + (p.age || 0); }, 0) / everyone.items.length
          : 0,
      };
      renderHero(summary || fallback, everyone.total);
      renderRecords(highest, longest);
      renderCensus(everyone.items, departments);
      renderLedger(departments);

      if (everyone.total > everyone.items.length) {
        $("#census").after(h("p", { class: "block-note" },
          "Showing the first " + nf.format(everyone.items.length) + " of " + nf.format(everyone.total) +
          " patients here. The directory below lists everyone."));
      }
      return true;
    });
  }

  function start() {
    return loadOverview().then(function (ok) {
      if (ok) return loadDirectory();
      $("#dir-count").textContent = "Directory unavailable";
      return null;
    });
  }

  bindTheme();
  bindDirectory();
  bindDrawer();
  updateSortHeaders();
  start();
})();
