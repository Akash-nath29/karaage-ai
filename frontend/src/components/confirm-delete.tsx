import { useState } from 'react'

import { Button } from '@/components/ui/button'

// Two-step delete instead of window.confirm(), which blocks the page.
export function ConfirmDelete({ label, onConfirm, pending }: { label: string; onConfirm: () => void; pending?: boolean }) {
  const [armed, setArmed] = useState(false)
  if (!armed)
    return (
      <Button variant="destructive" onClick={() => setArmed(true)}>
        {label}
      </Button>
    )
  return (
    <div className="flex items-center gap-2">
      <Button variant="destructive" onClick={onConfirm} pending={pending}>
        Confirm delete
      </Button>
      <Button variant="ghost" onClick={() => setArmed(false)}>
        Cancel
      </Button>
    </div>
  )
}
