import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());

// jsdom belum punya matchMedia / IntersectionObserver / <dialog>.showModal.
if (!window.matchMedia) {
  window.matchMedia = (q: string) =>
    ({ matches: false, media: q, onchange: null, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false }) as MediaQueryList;
}
if (!("IntersectionObserver" in window)) {
  (window as unknown as Record<string, unknown>).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() { return []; }
  };
}
const dlg = HTMLDialogElement.prototype as unknown as Record<string, unknown>;
dlg.showModal ??= function (this: HTMLDialogElement) { this.setAttribute("open", ""); };
dlg.close ??= function (this: HTMLDialogElement) { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); };
Element.prototype.scrollIntoView ??= () => {};
