import { useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { useCreateSession, type SessionContext } from '@/features/tutor/api'

/** Opens a new conversation about a course, topic or lesson. */
export function StartTutor({ context, label = 'Ask the tutor' }: { context: SessionContext; label?: string }) {
  const create = useCreateSession()
  const navigate = useNavigate()
  return (
    <>
      <Button variant="outline" disabled={create.isPending} onClick={() => create.mutate(context, { onSuccess: (s) => navigate(`/tutor/${s.id}`) })}>
        {label}
      </Button>
      {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
    </>
  )
}
