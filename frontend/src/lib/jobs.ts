import { useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

export type JobEvent = { stage: string; message: string; progress: number | null }

/** Live progress of a background job over SSE (native EventSource: same-origin GET, reconnects with
 * Last-Event-ID). When the job ends, `refresh` is invalidated so the page shows the final state. */
export function useJobProgress(jobId: string | null, active: boolean, refresh: QueryKey, alsoRefresh?: QueryKey) {
  const qc = useQueryClient()
  const [event, setEvent] = useState<JobEvent | null>(null)
  const key = JSON.stringify([refresh, ...(alsoRefresh ? [alsoRefresh] : [])]) // stable dependency for inline arrays
  useEffect(() => {
    if (!jobId || !active) return
    const source = new EventSource(`/api/v1/jobs/${jobId}/events`)
    source.onmessage = (e) => setEvent(JSON.parse(e.data))
    source.addEventListener('end', () => {
      source.close()
      for (const queryKey of JSON.parse(key)) qc.invalidateQueries({ queryKey })
    })
    return () => source.close()
  }, [jobId, active, qc, key])
  return event
}
