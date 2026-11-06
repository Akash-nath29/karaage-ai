import { fileUrl, type Passage } from '@/features/documents/api'

const pages = (p: Passage) =>
  p.page_start == null ? null : p.page_start === p.page_end ? `p. ${p.page_start}` : `pp. ${p.page_start}–${p.page_end}`

/** A passage from the student's materials, cited to its file and page (opens the source at that page). */
export function PassageCard({ passage: p }: { passage: Passage }) {
  return (
    <li className="grid gap-1.5 rounded-xl border p-4">
      <p className="text-sm">
        <a href={fileUrl(p.document_id, p.page_start)} target="_blank" rel="noreferrer" className="font-medium hover:underline">
          {p.filename}
          {pages(p) && `, ${pages(p)}`}
        </a>
        {p.heading_path && <span className="text-muted-foreground"> · {p.heading_path}</span>}
      </p>
      <p className="line-clamp-6 text-sm whitespace-pre-line">{p.content}</p>
    </li>
  )
}
