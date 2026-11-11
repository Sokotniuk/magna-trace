// Prints one element only (a handover). The element is marked for the print stylesheet and
// unmarked after printing; nothing is copied or sent anywhere.
export function printOnly(element: HTMLElement | null) {
  if (!element) return
  element.setAttribute('data-print', '')
  const done = () => {
    element.removeAttribute('data-print')
    window.removeEventListener('afterprint', done)
  }
  window.addEventListener('afterprint', done)
  window.print()
}
