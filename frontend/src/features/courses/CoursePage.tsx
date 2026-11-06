import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ConfirmDelete } from '@/components/confirm-delete'
import { SimpleForm } from '@/components/simple-form'
import { Button } from '@/components/ui/button'
import { PracticePanel } from '@/features/assessments/PracticePanel'
import { courseFields, useCourse, useDeleteCourse, useUpdateCourse } from '@/features/courses/api'
import { DocumentsPanel } from '@/features/documents/DocumentsPanel'
import { SearchPanel } from '@/features/documents/SearchPanel'
import { SyllabusPanel } from '@/features/syllabus/SyllabusPanel'
import { useRole } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'

export function CoursePage() {
  const { courseId = '' } = useParams()
  const course = useCourse(courseId)
  const update = useUpdateCourse(courseId)
  const remove = useDeleteCourse(courseId)
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const role = useRole(course.data?.workspace_id)

  if (course.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (course.error) return <p role="alert" className="text-destructive">{course.error.message}</p>
  const c = course.data
  const back = `/workspaces/${c.workspace_id}`

  return (
    <div className="grid gap-10">
      <section className="grid gap-4">
        <Link to={back} className="text-sm text-muted-foreground hover:underline">
          ← Back to workspace
        </Link>
        {editing ? (
          <div className="max-w-md">
            <SimpleForm
              fields={courseFields}
              initial={c}
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
              <h1 className="text-2xl font-semibold">{c.title}</h1>
              {(c.code || c.term) && (
                <p className="text-sm text-muted-foreground">{[c.code, c.term].filter(Boolean).join(' · ')}</p>
              )}
              {c.description && <p className="mt-2 max-w-prose">{c.description}</p>}
            </div>
            {atLeast(role, 'admin') && (
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <ConfirmDelete
                  label="Delete course"
                  pending={remove.isPending}
                  onConfirm={() => remove.mutate(undefined, { onSuccess: () => navigate(back) })}
                />
              </div>
            )}
          </div>
        )}
      </section>

      <SyllabusPanel course={c} />
      <PracticePanel courseId={c.id} workspaceId={c.workspace_id} />
      <DocumentsPanel workspaceId={c.workspace_id} courseId={c.id} />
      <SearchPanel workspaceId={c.workspace_id} courseId={c.id} />
    </div>
  )
}
