import katex from 'katex'
import type { ReactNode } from 'react'

import { MermaidDiagram } from '@/components/diagrams/mermaid-diagram'
import { Flashcards, Quiz } from '@/components/lesson-blocks/interactive'
import { Markdown } from '@/components/lesson-blocks/markdown'
import { fileUrl } from '@/features/documents/api'
import { citationLabel, type Block, type Citation } from '@/features/lessons/api'
import { cn } from '@/lib/utils'

const CALLOUT: Record<string, { label: string; className: string }> = {
  note: { label: 'Note', className: 'border-sky-600/40 bg-sky-50 dark:bg-sky-950/40' },
  tip: { label: 'Tip', className: 'border-emerald-600/40 bg-emerald-50 dark:bg-emerald-950/40' },
  warning: { label: 'Watch out', className: 'border-amber-600/50 bg-amber-50 dark:bg-amber-950/40' },
  exam: { label: 'Exam tip', className: 'border-violet-600/40 bg-violet-50 dark:bg-violet-950/40' },
}
// Practice and navigation blocks don't make claims, so they get no "AI-written" label.
const NO_PROVENANCE = new Set(['heading', 'quiz', 'flashcards'])

function Formula({ latex }: { latex: string }) {
  // KaTeX output with trust off is safe markup; same options as the backend check (D15).
  const html = katex.renderToString(latex, { displayMode: true, throwOnError: false, trust: false, strict: 'ignore' })
  return <div className="overflow-x-auto py-1" dangerouslySetInnerHTML={{ __html: html }} />
}

function DataTable({ caption, head, rows }: { caption: string; head: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="mb-2 text-left text-sm text-muted-foreground">{caption}</caption>}
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i} scope="col" className="border-b-2 px-3 py-2 text-left font-medium">
                <Markdown text={h} inline />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="border-b align-top">
              {row.map((cell, c) =>
                c === 0 ? (
                  <th key={c} scope="row" className="px-3 py-2 text-left font-medium">
                    <Markdown text={cell} inline />
                  </th>
                ) : (
                  <td key={c} className="px-3 py-2">
                    <Markdown text={cell} inline />
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Content({ block }: { block: Block }): ReactNode {
  switch (block.type) {
    case 'paragraph':
      return <Markdown text={block.markdown} />
    case 'heading':
      return <h4 className="mt-2 font-medium">{block.text}</h4>
    case 'concept':
      return (
        <div className="rounded-xl border-l-4 border-primary/60 bg-muted/40 px-4 py-3">
          <p className="font-medium">{block.term}</p>
          <Markdown text={block.markdown} />
        </div>
      )
    case 'diagram':
      return (
        <figure className="grid gap-2 rounded-xl border p-4">
          <MermaidDiagram source={block.source} label={block.caption || 'Diagram'} />
          {block.caption && <figcaption className="text-center text-sm text-muted-foreground">{block.caption}</figcaption>}
        </figure>
      )
    case 'table':
      return <DataTable caption={block.caption} head={block.headers} rows={block.rows} />
    case 'comparison':
      return <DataTable caption={block.caption} head={['', ...block.items]} rows={block.rows.map((r) => [r.aspect, ...r.values])} />
    case 'formula':
      return (
        <div className="grid gap-1">
          <Formula latex={block.latex} />
          {block.explanation && <Markdown text={block.explanation} className="text-sm text-muted-foreground" />}
        </div>
      )
    case 'code':
      return (
        <div className="grid gap-2">
          <pre className="overflow-x-auto rounded-xl bg-muted p-4 text-sm">
            <code>{block.code}</code>
          </pre>
          {block.explanation && <Markdown text={block.explanation} className="text-sm" />}
        </div>
      )
    case 'example':
      return (
        <div className="grid gap-2 rounded-xl border p-4">
          <p className="font-medium">{block.title || 'Example'}</p>
          <Markdown text={block.problem} />
          <details className="group">
            <summary className="cursor-pointer text-sm font-medium text-primary">Show the solution</summary>
            <Markdown text={block.solution} className="mt-2 border-l-2 pl-3" />
          </details>
        </div>
      )
    case 'callout': {
      const style = CALLOUT[block.variant] ?? CALLOUT.note
      return (
        <aside className={cn('rounded-xl border-l-4 px-4 py-3', style.className)}>
          <p className="text-sm font-medium">{style.label}</p>
          <Markdown text={block.markdown} />
        </aside>
      )
    }
    case 'steps':
      return (
        <div className="grid gap-2">
          {block.title && <p className="font-medium">{block.title}</p>}
          <ol className="grid list-decimal gap-1.5 pl-6">
            {block.steps.map((step, i) => (
              <li key={i}>
                <Markdown text={step} inline />
              </li>
            ))}
          </ol>
        </div>
      )
    case 'quiz':
      return <Quiz block={block} />
    case 'flashcards':
      return <Flashcards block={block} />
    case 'summary':
      return (
        <ul className="grid list-disc gap-1.5 pl-6">
          {block.points.map((point, i) => (
            <li key={i}>
              <Markdown text={point} inline />
            </li>
          ))}
        </ul>
      )
  }
}

export function CitationLink({ citation: c }: { citation: Citation }) {
  if (c.kind === 'web' && c.url)
    return (
      <a href={c.url} target="_blank" rel="noopener noreferrer nofollow" className="underline-offset-2 hover:underline">
        {citationLabel(c)}
      </a>
    )
  if (c.kind === 'material' && c.available && c.document_id)
    return (
      <a href={fileUrl(c.document_id, c.page_start)} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
        {citationLabel(c)}
      </a>
    )
  return <span title="The cited document was deleted; the quote is kept below">{citationLabel(c)} (removed)</span>
}

/** One lesson block with its provenance: your materials, the web, or AI-written (PRD §11.2). */
export function LessonBlock({ block, citations }: { block: Block; citations: Map<string, Citation> }) {
  const cited = block.citations.map((label) => citations.get(label)).filter((c): c is Citation => !!c)
  return (
    <div className="grid gap-1.5">
      <Content block={block} />
      {!NO_PROVENANCE.has(block.type) && (
        <p className="text-xs text-muted-foreground">
          {cited.length ? (
            <>
              {cited.some((c) => c.kind === 'material') ? 'From your materials' : 'From the web'}:{' '}
              {cited.map((c, i) => (
                <span key={c.label}>
                  {i > 0 && ' · '}
                  <CitationLink citation={c} />
                </span>
              ))}
            </>
          ) : (
            'AI-written explanation'
          )}
        </p>
      )}
    </div>
  )
}
