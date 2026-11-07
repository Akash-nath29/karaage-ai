import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router'

import { ConfirmDelete } from '@/components/confirm-delete'
import { RouteTabs } from '@/components/route-tabs'
import { SimpleForm } from '@/components/simple-form'
import { Button } from '@/components/ui/button'
import { courseFields, useCourses, useCreateCourse, type Course, type CourseInput } from '@/features/courses/api'
import { CourseRow } from '@/features/courses/CourseRow'
import { DocumentsPanel } from '@/features/documents/DocumentsPanel'
import { SearchPanel } from '@/features/documents/SearchPanel'
import { useDeleteWorkspace, useUpdateWorkspace, useWorkspace, workspaceFields, type Workspace } from '@/features/workspaces/api'
import { MembersPanel } from '@/features/workspaces/MembersPanel'
import { SharedLessons, UsagePanel } from '@/features/workspaces/OverviewPanels'
import { atLeast } from '@/lib/api'

/** Screen 2 (D38): a workspace leads with its courses, the way into studying; lessons, materials, members and usage
 * are tabs beside them. */
export function WorkspacePage() {
  const { workspaceId = '' } = useParams()
  const workspace = useWorkspace(workspaceId)
  const courses = useCourses(workspaceId)
  const update = useUpdateWorkspace(workspaceId)
  const remove = useDeleteWorkspace(workspaceId)
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)

  if (workspace.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (workspace.error) return <p role="alert" className="text-destructive">{workspace.error.message}</p>
  const w = workspace.data
  const admin = atLeast(w.role, 'admin')
  const base = `/workspaces/${w.id}`

  return (
    <div className="grid gap-8">
      <header className="grid gap-2">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link to="/" className="hover:text-foreground hover:underline">
            Home
          </Link>
        </nav>
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
              <h1 className="text-2xl font-semibold tracking-tight text-balance">{w.name}</h1>
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
                <ConfirmDelete label="Delete workspace" pending={remove.isPending}
                               onConfirm={() => remove.mutate(undefined, { onSuccess: () => navigate('/') })} />
              )}
            </div>
          </div>
        )}
      </header>

      <div className="grid gap-8">
        <RouteTabs
          label="Workspace"
          tabs={[
            { to: base, end: true, label: 'Courses' },
            { to: `${base}/lessons`, label: 'Shared lessons' },
            { to: `${base}/materials`, label: 'Materials' },
            { to: `${base}/members`, label: 'Members' },
            { to: `${base}/usage`, label: 'AI usage' },
          ]}
        />
        <Routes>
          <Route index element={<WorkspaceCourses workspace={w} courses={courses.data} error={courses.error} />} />
          <Route path="lessons" element={<SharedLessons workspaceId={w.id} />} />
          <Route
            path="materials"
            element={
              <div className="grid gap-12">
                <DocumentsPanel workspaceId={w.id} courses={courses.data} />
                <SearchPanel workspaceId={w.id} />
              </div>
            }
          />
          <Route path="members" element={<MembersPanel workspaceId={w.id} role={w.role} />} />
          <Route path="usage" element={<UsagePanel workspaceId={w.id} />} />
          <Route path="*" element={<Navigate to={base} replace />} />
        </Routes>
      </div>
    </div>
  )
}

function WorkspaceCourses({ workspace: w, courses, error }: { workspace: Workspace; courses?: Course[]; error: Error | null }) {
  const admin = atLeast(w.role, 'admin')
  const create = useCreateCourse(w.id)
  const navigate = useNavigate()
  const [adding, setAdding] = useState(false)

  return (
    <section aria-labelledby="courses-title" className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="courses-title" className="text-lg font-medium">Courses</h2>
        {admin && !adding && (
          <Button variant="outline" onClick={() => setAdding(true)}>
            <Plus />
            New course
          </Button>
        )}
      </div>
      {adding && (
        <div className="grid max-w-md gap-3 rounded-xl border p-5">
          <p className="text-sm text-muted-foreground">Use the title and code as they appear on the syllabus. You'll set up its syllabus and materials next.</p>
          <SimpleForm
            fields={courseFields}
            submitLabel="Create course"
            pending={create.isPending}
            error={create.error}
            onSubmit={async (v) => navigate(`/courses/${(await create.mutateAsync(v as CourseInput)).id}`)}
            onCancel={() => setAdding(false)}
          />
        </div>
      )}
      {error && <p role="alert" className="text-destructive">{error.message}</p>}
      {courses?.length === 0 && !adding && (
        <p className="text-muted-foreground">
          No courses yet.{' '}
          {admin ? 'Add one and Karaage walks you through its syllabus, materials and lessons.' : 'An admin of this workspace adds them.'}
        </p>
      )}
      {!!courses?.length && (
        <ul className="divide-y rounded-xl border">
          {courses.map((c) => (
            <CourseRow key={c.id} id={c.id} title={c.title} detail={[c.code, c.term].filter(Boolean).join(' · ') || undefined} />
          ))}
        </ul>
      )}
    </section>
  )
}
