// Adds DOM matchers such as expect(element).toBeInTheDocument() to Vitest.
import '@testing-library/jest-dom/vitest'

// jsdom lacks a few browser APIs that Mantine uses (media queries, element resizing).
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: query.includes('min-width'), // behave like a wide desktop screen
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
window.HTMLElement.prototype.scrollIntoView = () => {}
// Mantine's auto-growing Textarea re-measures when web fonts load.
Object.defineProperty(document, 'fonts', {
  value: { addEventListener: () => {}, removeEventListener: () => {} },
})
