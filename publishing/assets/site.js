(() => {
  const root = document.documentElement;
  const themeButton = document.querySelector("[data-theme-toggle]");
  const themeLabel = document.querySelector("[data-theme-label]");
  const themeQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const storageKey = "agent-security-insights-theme";

  const updateThemeLabel = () => {
    if (!themeButton) return;
    const next = root.dataset.theme === "dark" ? "日间" : "夜间";
    const label = `切换到${next}模式`;
    themeButton.setAttribute("aria-label", label);
    themeButton.setAttribute("aria-pressed", root.dataset.theme === "dark" ? "true" : "false");
    if (themeLabel) themeLabel.textContent = label;
  };

  updateThemeLabel();
  themeButton?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    localStorage.setItem(storageKey, next);
    updateThemeLabel();
  });
  themeQuery.addEventListener("change", (event) => {
    if (localStorage.getItem(storageKey)) return;
    root.dataset.theme = event.matches ? "dark" : "light";
    updateThemeLabel();
  });

  const toggle = document.querySelector("[data-page-toc-toggle]");
  const toc = document.querySelector("[data-page-toc]");
  const overlay = document.querySelector("[data-site-overlay]");

  const closeToc = () => {
    if (!toggle || !toc || !overlay) return;
    toc.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    overlay.hidden = true;
    document.body.classList.remove("drawer-open");
  };

  const openToc = () => {
    if (!toggle || !toc || !overlay) return;
    toc.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    overlay.hidden = false;
    document.body.classList.add("drawer-open");
    toc.querySelector("a")?.focus();
  };

  toggle?.addEventListener("click", () => {
    if (toc?.classList.contains("is-open")) closeToc();
    else openToc();
  });
  overlay?.addEventListener("click", closeToc);
  toc?.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeToc();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeToc();
  });

  const tocLinks = new Map(
    [...document.querySelectorAll(".issue-toc a[href^='#']")].map((link) => [
      decodeURIComponent(link.hash.slice(1)),
      link,
    ])
  );
  const headings = [...document.querySelectorAll(".report-content h2[id], .report-content h3[id]")];
  if (tocLinks.size && headings.length && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => left.boundingClientRect.top - right.boundingClientRect.top);
        if (!visible.length) return;
        tocLinks.forEach((link) => link.removeAttribute("aria-current"));
        tocLinks.get(visible[0].target.id)?.setAttribute("aria-current", "location");
      },
      { rootMargin: "-15% 0px -72%", threshold: [0, 1] }
    );
    headings.forEach((heading) => observer.observe(heading));
  }
})();
