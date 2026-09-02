import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface ClientContextType {
  clientCode: string | null
  setClientCode: (code: string) => void
  clearClientCode: () => void
}

const ClientContext = createContext<ClientContextType | undefined>(undefined)

export function ClientProvider({ children }: { children: ReactNode }) {
  const [clientCode, setClientCodeState] = useState<string | null>(() => {
    // 從 localStorage 讀取
    return localStorage.getItem('client_code')
  })

  const setClientCode = (code: string) => {
    setClientCodeState(code)
    localStorage.setItem('client_code', code)
  }

  const clearClientCode = () => {
    setClientCodeState(null)
    localStorage.removeItem('client_code')
  }

  return (
    <ClientContext.Provider value={{ clientCode, setClientCode, clearClientCode }}>
      {children}
    </ClientContext.Provider>
  )
}

export function useClient() {
  const context = useContext(ClientContext)
  if (context === undefined) {
    throw new Error('useClient must be used within a ClientProvider')
  }
  return context
}
