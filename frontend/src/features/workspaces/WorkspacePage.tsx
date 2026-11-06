import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ConfirmDelete } from '@/components/confirm-delete'
import { SimpleForm } from '@/components/simple-form'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { courseFields, useCourses, useCreateCourse, type CourseInput } from '@/features/courses/api'
import { DocumentsPanel } from '@/features/documents/DocumentsPanel'
import { SearchPanel } from '@/features/documents/SearchPanel'
import { useDeleteWorkspace, useUpdateWorkspace, useWorkspace, workspaceFields } from '@/features/workspaces/api'
import { MembersPanel } from '@/features/workspaces/MembersPanel'
import { SharedLessons, UsagePanel } from '@/features/workspaces/OverviewPanels'
import { atLeast } from '@/lib/api'

export function WorkspacePage() {
  const { workspaceId = '' } = useParams()
  const workspace = useWorkspace(workspaceId)
  const courses = useCourses(workspaceId)
  const update = useUpdateWorkspace(workspaceId)
  const remove = useDeleteWorkspace(workspaceId)
  const createCourse = useCreateCourse(workspaceId)
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)

  if (workspace.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (workspace.error) return <p role="alert" className="text-destructive">{workspace.error.message}</p>
  const w = workspace.data
  const admin = atLeast(w.role, 'admin')

  return (
    <div className="grid gap-10">
      <section className="grid gap-4">
        <Link to="/" className="text-sm text-muted-foreground hover:underline">
          ← All workspaces
        </Link>
        {editing ? (
          <div className="max-w-md">
            <SimpleForm
              fields={workspaceFields}
              initial={w}
              submitLabel="Save"
              pending={update.isPending}
              error={update.error}
              onSubmit={async (v) => {
                await update.mutateAsync(v)
                setEditing(false)
              }}
              onCancel={() => setEditing(false)}
            />
          </div>
        ) : (
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="grid gap-1">
              <h1 className="text-2xl font-semibold">{w.name}</h1>
              {w.description && <p className="max-w-prose text-muted-foreground">{w.description}</p>}
              <p className="text-sm text-muted-foreground">Your role: {w.role}</p>
            </div>
            <div className="flex gap-2">
              {admin && (
                <Button variant="outline" onClick={() => setEditing(true)}>
                  Edit
                </Button>
              )}
              {w.role === 'owner' && (
                <ConfirmDelete
                  label="Delete workspace"
                  pending={remove.isPending}
                  onConfirm={() => remove.mutate(undefined, { onSuccess: () => navigate('/') })}
                />
              )}
            </div>
          </div>
        )}
      </section>

      <section className="grid gap-4">
        <h2 className="text-lg font-medium">Courses</h2>
        {courses.error && <p role="alert" className="text-destructive">{courses.error.message}</p>}
        {courses.data?.length === 0 && <p className="text-muted-foreground">No courses in this workspace yet.</p>}
        <ul className="grid gap-3 sm:grid-cols-2">
          {courses.data?.map((c) => (
            <li key={c.id}>
              <Link to={`/courses/${c.id}`} className="block rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 outline-none">
                <Card className="h-full transition-colors hover:bg-muted/50">
                  <CardHeader>
                    <CardTitle>{c.title}</CardTitle>
                    <CardDescription>{[c.code, c.term].filter(Boolean).join(' · ') || 'No code or term'}</CardDescription>
                  </CardHeader>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {admin && <section className="grid max-w-md gap-4">
        <h2 className="text-lg font-medium">New course</h2>
        <SimpleForm
          fields={courseFields}
          submitLabel="Create course"
          pending={createCourse.isPending}
          error={createCourse.error}
          onSubmit={(v) => createCourse.mutateAsync(v as CourseInput)}
        />
      </section>}

      <SharedLessons workspaceId={workspaceId} />

      <DocumentsPanel workspaceId={workspaceId} courses={courses.data} />
      <SearchPanel workspaceId={workspaceId} />
      <MembersPanel workspaceId={workspaceId} role={w.role} />
      <UsagePanel workspaceId={workspaceId} />
    </div>
  )
}
