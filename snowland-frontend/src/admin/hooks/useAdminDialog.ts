import { useEffect, useRef } from 'react'

/** Keep keyboard and scroll inside an open admin dialog, then return to its trigger. */
export function useAdminDialog(open: boolean, busy: boolean, onClose: () => void) {
  const dialog = useRef<HTMLElement | null>(null)
  const controls = useRef({ busy, onClose })
  controls.current = { busy, onClose }

  useEffect(() => {
    const panel = dialog.current
    if (!open || !panel) return
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    const focusable = () => Array.from(panel.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), summary, a[href], [tabindex="0"]',
    )).filter(element => !element.closest('[hidden], [inert]') && element.getClientRects().length > 0)
    document.body.style.overflow = 'hidden'
    ;(focusable()[0] || panel).focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        if (!controls.current.busy) controls.current.onClose()
      } else if (event.key === 'Tab') {
        const items = focusable(), first = items[0], last = items[items.length - 1]
        if (!first) { event.preventDefault(); panel.focus(); return }
        if (!panel.contains(document.activeElement) || document.activeElement === panel) {
          event.preventDefault(); (event.shiftKey ? last : first).focus()
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus()
        }
      }
    }
    document.addEventListener('keydown', keydown)
    return () => {
      document.removeEventListener('keydown', keydown)
      document.body.style.overflow = overflow
      if (previous?.isConnected) previous.focus()
    }
  }, [open])
  return dialog
}
