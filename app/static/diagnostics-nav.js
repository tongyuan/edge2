(function diagnosticsNavigationModule(globalScope) {
  "use strict";

  function setupDiagnosticsNavigation(navigation, documentRef = globalScope.document) {
    const trigger = navigation.querySelector("[data-diagnostics-trigger]");
    const menu = navigation.querySelector("[data-diagnostics-menu]");
    const items = Array.from(menu.querySelectorAll('a[role="menuitem"]'));

    function isOpen() {
      return trigger.getAttribute("aria-expanded") === "true";
    }

    function openMenu(focusIndex = null) {
      menu.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      if (focusIndex !== null && items.length) {
        items[focusIndex < 0 ? items.length - 1 : focusIndex].focus();
      }
    }

    function closeMenu({ restoreFocus = false } = {}) {
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
      if (restoreFocus) trigger.focus();
    }

    function onTriggerClick() {
      if (isOpen()) closeMenu();
      else openMenu();
    }

    function onTriggerKeydown(event) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        openMenu(event.key === "ArrowUp" ? -1 : 0);
      }
    }

    function onMenuKeydown(event) {
      const currentIndex = items.indexOf(documentRef.activeElement);
      let nextIndex = null;
      if (event.key === "ArrowDown") nextIndex = (currentIndex + 1) % items.length;
      if (event.key === "ArrowUp") nextIndex = (currentIndex - 1 + items.length) % items.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = items.length - 1;
      if (nextIndex !== null && items.length) {
        event.preventDefault();
        items[nextIndex].focus();
      }
    }

    function onDocumentClick(event) {
      if (isOpen() && !navigation.contains(event.target)) closeMenu();
    }

    function onDocumentKeydown(event) {
      if (event.key === "Escape" && isOpen()) {
        event.preventDefault();
        closeMenu({ restoreFocus: true });
      }
    }

    trigger.addEventListener("click", onTriggerClick);
    trigger.addEventListener("keydown", onTriggerKeydown);
    menu.addEventListener("keydown", onMenuKeydown);
    items.forEach((item) => item.addEventListener("click", () => closeMenu()));
    documentRef.addEventListener("click", onDocumentClick);
    documentRef.addEventListener("keydown", onDocumentKeydown);

    return { closeMenu, isOpen, openMenu };
  }

  function initializeDiagnosticsNavigation(documentRef = globalScope.document) {
    if (!documentRef) return [];
    return Array.from(documentRef.querySelectorAll("[data-diagnostics-nav]"))
      .map((navigation) => setupDiagnosticsNavigation(navigation, documentRef));
  }

  const exported = { initializeDiagnosticsNavigation, setupDiagnosticsNavigation };
  if (typeof module !== "undefined" && module.exports) module.exports = exported;
  globalScope.EdgeDiagnosticsNavigation = exported;

  if (globalScope.document) initializeDiagnosticsNavigation(globalScope.document);
})(typeof globalThis !== "undefined" ? globalThis : this);
