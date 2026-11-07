import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { SimpleForm } from '@/components/simple-form'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useCreateWorkspace, useWorkspaces, workspaceFields, type WorkspaceInput } from '@/features/workspaces/api'

/** Your workspaces, and a new one on demand (the first-visit path on the dashboard has its own form). */
export function WorkspacesPage() {
  const workspaces = useWorkspaces()
  const create = useCreateWorkspace()
  const navigate = useNavigate()
  const [adding, setAdding] = useState(false)

  return (
    <section aria-labelledby="workspaces-title" className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="workspaces-title" className="text-lg font-medium">Workspaces</h2>
        {!adding && (
          <Button variant="outline" onClick={() => setAdding(true)}>
            <Plus />
            New workspace
          </Button>
        )}
      </div>
      {adding && (
        <div className="max-w-md rounded-xl border p-5">
          <SimpleForm
            fields={workspaceFields}
            submitLabel="Create workspace"
            pending={create.isPending}
            error={create.error}
            onSubmit={async (v) => navigate(`/workspaces/${(await create.mutateAsync(v as WorkspaceInput)).id}`)}
            onCancel={() => setAdding(false)}
          />
        </div>
      )}
      {workspaces.isPending && <p className="text-muted-foreground">Loading…</p>}
      {workspaces.error && <p role="alert" className="text-destructive">{workspaces.error.message}</p>}
      {!!workspaces.data?.length && (
        <ul className="divide-y rounded-xl border">
          {workspaces.data.map((w) => (
            <li key={w.id}>
              <Link to={`/workspaces/${w.id}`}
                    className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50">
                <span className="grid min-w-0 gap-0.5">
                  <span className="font-medium">{w.name}</span>
                  {w.description && <span className="line-clamp-1 text-sm text-muted-foreground">{w.description}</span>}
                </span>
                <Badge variant={w.role === 'owner' ? 'default' : 'secondary'}>{w.role}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
