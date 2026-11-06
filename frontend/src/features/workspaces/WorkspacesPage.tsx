import { Link, useNavigate } from 'react-router'

import { SimpleForm } from '@/components/simple-form'
import { Badge } from '@/components/ui/badge'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useCreateWorkspace, useWorkspaces, workspaceFields, type WorkspaceInput } from '@/features/workspaces/api'

export function WorkspacesPage() {
  const workspaces = useWorkspaces()
  const create = useCreateWorkspace()
  const navigate = useNavigate()

  return (
    <div className="grid gap-10">
      <section className="grid gap-4">
        <h2 className="text-lg font-medium">Your workspaces</h2>
        {workspaces.isPending && <p className="text-muted-foreground">Loading…</p>}
        {workspaces.error && <p role="alert" className="text-destructive">{workspaces.error.message}</p>}
        {workspaces.data?.length === 0 && (
          <p className="text-muted-foreground">
            No workspaces yet. Create one to hold your courses and study material, or open an invitation link someone sent you.
          </p>
        )}
        <ul className="grid gap-3 sm:grid-cols-2">
          {workspaces.data?.map((w) => (
            <li key={w.id}>
              <Link to={`/workspaces/${w.id}`} className="block rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 outline-none">
                <Card className="h-full transition-colors hover:bg-muted/50">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between gap-2">
                      {w.name}
                      <Badge variant={w.role === 'owner' ? 'default' : 'secondary'}>{w.role}</Badge>
                    </CardTitle>
                    {w.description && <CardDescription className="line-clamp-2">{w.description}</CardDescription>}
                  </CardHeader>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid max-w-md gap-4">
        <h2 className="text-lg font-medium">New workspace</h2>
        <SimpleForm
          fields={workspaceFields}
          submitLabel="Create workspace"
          pending={create.isPending}
          error={create.error}
          onSubmit={async (v) => navigate(`/workspaces/${(await create.mutateAsync(v as WorkspaceInput)).id}`)}
        />
      </section>
    </div>
  )
}
