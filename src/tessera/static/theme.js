/* Apply the saved colour theme before first paint so there is no flash. */
(function () {
  try {
    var saved = localStorage.getItem("patient-theme");
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (e) {
    /* storage unavailable: fall back to the system preference via CSS */
  }
})();
