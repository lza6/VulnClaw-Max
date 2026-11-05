import "@testing-library/jest-dom/vitest";

// jsdom in some Node versions exposes a localStorage without clear(); prefer a
// deterministic in-memory implementation for the test suite.
const values = new Map<string, string>();
const storage: Storage = {
  get length() {
    return values.size;
  },
  clear() {
    values.clear();
  },
  getItem(key: string) {
    return values.has(key) ? (values.get(key) as string) : null;
  },
  key(index: number) {
    return Array.from(values.keys())[index] ?? null;
  },
  removeItem(key: string) {
    values.delete(key);
  },
  setItem(key: string, value: string) {
    values.set(key, String(value));
  },
};

Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: storage,
});
