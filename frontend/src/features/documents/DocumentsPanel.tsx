import { useId, useState } from 'react'

import { ConfirmDelete } from '@/components/confirm-delete'
import { NativeSelect } from '@/components/native-select'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import type { Course } from '@/features/courses/api'
import {
  ACCEPT,
  KINDS,
  fileUrl,
  formatSize,
  useDeleteDocument,
  useDocuments,
  useReprocessDocument,
  useUpdateDocument,
  useUploadDocument,
  type Document,
  type DocumentKind,
} from '@/features/documents/api'
import { JobProgress } from '@/components/job-progress'
import { useMe } from '@/features/auth/api'
import { useRole } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'
import { useJobProgress } from '@/lib/jobs'

type Props = {
  workspaceId: string
  /** On a course page: list and upload only that course's documents. */
  courseId?: string
  /** On a workspace page: lets each document be assigned to a course. */
  courses?: Course[]
}

export function DocumentsPanel({ workspaceId, courseId, courses }: Props) {
  const documents = useDocuments(workspaceId, courseId)
  const role = useRole(workspaceId)
  const me = useMe().data
  // A11: editors upload and manage their own uploads; admins and the owner manage every document.
  const canManage = (d: Document) => atLeast(role, 'admin') || (atLeast(role, 'editor') && d.uploaded_by === me?.id)
  return (
    <section className="grid gap-4" aria-labelledby="documents-heading">
      <h2 id="documents-heading" className="text-lg font-medium">
        Study materials
      </h2>
      {atLeast(role, 'editor') && <UploadForm workspaceId={workspaceId} courseId={courseId} courses={courses} />}
      {documents.error && <p role="alert" className="text-destructive">{documents.error.message}</p>}
      {documents.data?.length === 0 && <p className="text-muted-foreground">No materials uploaded yet.</p>}
      {!!documents.data?.length && (
        <ul className="divide-y rounded-xl border">
          {documents.data.map((d) => (
            <DocumentRow key={d.id} document={d} courses={courses} canManage={canManage(d)} />
          ))}
        </ul>
      )}
    </section>
  )
}

function UploadForm({ workspaceId, courseId, courses }: Props) {
  const id = useId()
  const upload = useUploadDocument(workspaceId)
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  return (
    <form
      className="grid gap-3 rounded-xl border p-4"
      onSubmit={async (e) => {
        e.preventDefault()
        const form = e.currentTarget
        const data = new FormData(form)
        const files = data.getAll('files') as File[]
        const kind = data.get('kind') as DocumentKind
        const course = courseId ?? ((data.get('course') as string) || undefined)
        setBusy(true)
        const failed: string[] = []
        for (const file of files) {
          // One request per file: one bad file doesn't block the rest, and each error names its file.
          await upload.mutateAsync({ file, kind, courseId: course }).catch((err: Error) => failed.push(`${file.name}: ${err.message}`))
        }
        setBusy(false)
        setErrors(failed)
        form.reset()
      }}
    >
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}files`}>Upload files</Label>
        <input
          id={`${id}files`}
          name="files"
          type="file"
          multiple
          required
          accept={ACCEPT}
          className="text-sm file:mr-3 file:rounded-lg file:border file:border-input file:bg-transparent file:px-2.5 file:py-1 file:text-sm file:font-medium"
        />
        <p className="text-xs text-muted-foreground">PDF, Word, PowerPoint, text, Markdown or images (scans are OCR'd).</p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}kind`}>Type</Label>
          <NativeSelect id={`${id}kind`} name="kind" defaultValue="notes">
            {KINDS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        {!courseId && !!courses?.length && (
          <div className="grid gap-1.5">
            <Label htmlFor={`${id}course`}>Course</Label>
            <NativeSelect id={`${id}course`} name="course" defaultValue="">
              <option value="">Whole workspace</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </NativeSelect>
          </div>
        )}
        <Button type="submit" disabled={busy}>
          {busy ? 'Uploading…' : 'Upload'}
        </Button>
      </div>
      {errors.length > 0 && (
        <ul role="alert" className="grid gap-1 text-sm text-destructive">
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
    </form>
  )
}

function DocumentRow({ document: d, courses, canManage }: { document: Document; courses?: Course[]; canManage: boolean }) {
  const busy = d.status === 'queued' || d.status === 'processing'
  const progress = useJobProgress(d.job_id, busy, ['documents'])
  const update = useUpdateDocument()
  const reprocess = useReprocessDocument()
  const remove = useDeleteDocument()
  const kind = KINDS.find(([value]) => value === d.kind)?.[1] ?? d.kind
  const facts = [kind, d.file_type.toUpperCase(), formatSize(d.size_bytes)]
  if (d.page_count) facts.push(`${d.page_count} ${d.file_type === 'pptx' ? 'slides' : 'pages'}`)
  if (d.status === 'ready') facts.push(`${d.chunk_count} ${d.chunk_count === 1 ? 'passage' : 'passages'}`)

  return (
    <li className="grid gap-2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid min-w-0 gap-0.5">
          <a href={fileUrl(d.id)} target="_blank" rel="noreferrer" className="truncate font-medium hover:underline">
            {d.filename}
          </a>
          <p className="text-sm text-muted-foreground">{facts.join(' · ')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {courses && canManage && (
            <NativeSelect
              aria-label={`Course for ${d.filename}`}
              value={d.course_id ?? ''}
              onChange={(e) => update.mutate({ id: d.id, course_id: e.target.value || null })}
            >
              <option value="">Whole workspace</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </NativeSelect>
          )}
          {canManage && (d.status === 'ready' || d.status === 'failed') && (
            <Button variant="outline" onClick={() => reprocess.mutate(d.id)} disabled={reprocess.isPending}>
              Reprocess
            </Button>
          )}
          {canManage && <ConfirmDelete label="Delete" pending={remove.isPending} onConfirm={() => remove.mutate(d.id)} />}
        </div>
      </div>
      {busy && <JobProgress event={progress} label={`Processing ${d.filename}`} />}
      {d.status === 'failed' && (
        <p role="alert" className="text-sm text-destructive">
          {d.error}
        </p>
      )}
      {(update.error || reprocess.error) && (
        <p role="alert" className="text-sm text-destructive">
          {(update.error ?? reprocess.error)?.message}
        </p>
      )}
    </li>
  )
}
