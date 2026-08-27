const assert = require("node:assert/strict");
const {
  setupDiagnosticsNavigation,
} = require("../app/static/diagnostics-nav.js");

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  dispatch(type, event = {}) {
    const dispatched = {
      target: this,
      key: undefined,
      defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; },
      ...event,
    };
    (this.listeners.get(type) || []).forEach((listener) => listener(dispatched));
    return dispatched;
  }
}

class FakeElement extends FakeEventTarget {
  constructor(documentRef) {
    super();
    this.attributes = new Map();
    this.documentRef = documentRef;
    this.hidden = false;
  }

  focus() {
    this.documentRef.activeElement = this;
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
}

class FakeDocument extends FakeEventTarget {
  constructor() {
    super();
    this.activeElement = null;
  }
}

function fixture() {
  const documentRef = new FakeDocument();
  const trigger = new FakeElement(documentRef);
  const menu = new FakeElement(documentRef);
  const items = [0, 1, 2].map(() => new FakeElement(documentRef));
  const members = new Set([trigger, menu, ...items]);
  const navigation = {
    querySelector(selector) {
      if (selector === "[data-diagnostics-trigger]") return trigger;
      if (selector === "[data-diagnostics-menu]") return menu;
      return null;
    },
    contains(target) { return members.has(target); },
  };
  menu.querySelectorAll = (selector) => (
    selector === 'a[role="menuitem"]' ? items : []
  );
  trigger.setAttribute("aria-expanded", "false");
  menu.hidden = true;
  return {
    controller: setupDiagnosticsNavigation(navigation, documentRef),
    documentRef,
    items,
    menu,
    trigger,
  };
}

{
  const { controller, menu, trigger } = fixture();
  assert.equal(controller.isOpen(), false);
  trigger.dispatch("click");
  assert.equal(controller.isOpen(), true);
  assert.equal(menu.hidden, false);
  trigger.dispatch("click");
  assert.equal(controller.isOpen(), false);
  assert.equal(menu.hidden, true);
}

{
  const { controller, documentRef, menu, trigger } = fixture();
  trigger.dispatch("click");
  documentRef.dispatch("click", { target: {} });
  assert.equal(controller.isOpen(), false);
  assert.equal(menu.hidden, true);
}

{
  const { controller, documentRef, trigger } = fixture();
  trigger.dispatch("click");
  const escape = documentRef.dispatch("keydown", { key: "Escape" });
  assert.equal(escape.defaultPrevented, true);
  assert.equal(controller.isOpen(), false);
  assert.equal(documentRef.activeElement, trigger);
}

{
  const { controller, documentRef, items, menu, trigger } = fixture();
  const openFromKeyboard = trigger.dispatch("keydown", { key: "ArrowDown" });
  assert.equal(openFromKeyboard.defaultPrevented, true);
  assert.equal(controller.isOpen(), true);
  assert.equal(documentRef.activeElement, items[0]);

  menu.dispatch("keydown", { key: "ArrowDown" });
  assert.equal(documentRef.activeElement, items[1]);
  menu.dispatch("keydown", { key: "End" });
  assert.equal(documentRef.activeElement, items[2]);
  menu.dispatch("keydown", { key: "Home" });
  assert.equal(documentRef.activeElement, items[0]);

  const selectItem = items[0].dispatch("click");
  assert.equal(selectItem.defaultPrevented, false, "menu item navigation remains native");
  assert.equal(controller.isOpen(), false);
}

console.log("diagnostics navigation tests passed");
