import "@testing-library/jest-dom/vitest";
import { webcrypto } from "node:crypto";

// Some stores use crypto.randomUUID(). Ensure it's available in jsdom.
if (!globalThis.crypto?.randomUUID) {
  globalThis.crypto = webcrypto as unknown as Crypto;
}

if (!Element.prototype.scrollIntoView) {
  // jsdom doesn't implement scroll APIs.
  Element.prototype.scrollIntoView = () => undefined;
}

