import { useMemo } from 'react'
import { clientCodeFromPath } from './utils/tenant'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App.tsx'
import { SiteLocaleProvider } from './contexts/SiteLocale'
import './index.css'

function TenantApplication() {
  const {pathname} = useLocation()
  const tenant = clientCodeFromPath(pathname) || 'public'
  const queryClient = useMemo(() => new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30 * 1000, // 30 秒
    },
  },
}), [tenant])
  return <QueryClientProvider client={queryClient}><SiteLocaleProvider><App key={tenant} /></SiteLocaleProvider></QueryClientProvider>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter><TenantApplication /></BrowserRouter>
  </React.StrictMode>,
)
