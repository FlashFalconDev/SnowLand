import { useParams } from 'react-router-dom'

/**
 * Returns the base path for site (brand website) pages.
 * All site page links should prepend this to their paths.
 *
 * Example: basePath = "/snowland"
 *   useSiteLink("/course/tomamu") => "/snowland/course/tomamu"
 */
export function useSiteBasePath(): string {
  const { clientCode } = useParams<{ clientCode: string }>()
  return clientCode ? `/${clientCode}` : ''
}

export function useSiteLink(path: string): string {
  const basePath = useSiteBasePath()
  // Ensure path starts with /
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${basePath}${normalizedPath}`
}
