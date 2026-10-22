import { useEffect, useState } from 'react'
import { fetchCourseCategories } from '@/api/booking'

export default function useCourseCategories(service: 'ski' | 'photo' | '') {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{service: string; status: 'loading' | 'ready' | 'error'; data: any[]}>(
    {service: '', status: 'ready', data: []},
  )
  useEffect(() => {
    if (!service) return
    let active = true
    setResult({service, status: 'loading', data: []})
    fetchCourseCategories(service).then(data => {
      if (active) setResult({service, status: 'ready', data: Array.isArray(data) ? data : []})
    }).catch(() => {
      if (active) setResult({service, status: 'error', data: []})
    })
    return () => { active = false }
  }, [service, attempt])
  return {
    categories: service && result.service === service ? result.data : [],
    status: !service ? 'ready' as const : result.service === service ? result.status : 'loading' as const,
    retry: () => setAttempt(value => value + 1),
  }
}
