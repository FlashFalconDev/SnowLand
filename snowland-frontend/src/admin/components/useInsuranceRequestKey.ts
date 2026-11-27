import { useRef } from 'react'

/** Reuse the key when retrying an unchanged submission after a network failure. */
export function useInsuranceRequestKey() {
  const last = useRef<{ payload: string; key: string }>()
  return {
    forPayload(data: object) {
      const payload = JSON.stringify(data)
      if (last.current?.payload !== payload) last.current = { payload, key: crypto.randomUUID() }
      return last.current.key
    },
    reset() {
      last.current = undefined
    },
  }
}
