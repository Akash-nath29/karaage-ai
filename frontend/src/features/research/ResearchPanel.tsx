import { useId } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SOURCE_TYPE, useLatestResearch, useSources, useStartResearch, type ClaimStatus, type Research, type Source } from '@/features/research/api'
import { JobProgress } from '@/components/job-progress'
import { useJobProgress } from '@/lib/jobs'

const CLAIM_BADGE: Record<ClaimStatus, { label: string; variant: 'secondary' | 'outline' | 'destructive' }> = {
  verified: { label: 'Verified', variant: 'secondary' },
  unverified: { label: 'Single source', variant: 'outline' },
  disputed: { label: 'Disputed', variant: 'destructive' },
}

export function ResearchPanel({ topicId }: { topicId: string }) {
  const id = useId()
  const latest = useLatestResearch(topicId)
  const start = useStartResearch(topicId)
  const r = latest.data
  const running = r?.status === 'queued' || r?.status === 'running'
  const progress = useJobProgress(r?.job_id ?? null, running, ['research', topicId])

  return (
    <section className="grid gap-4" aria-labelledby={`${id}heading`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={`${id}heading`} className="text-lg font-medium">
          Web research
        </h2>
        <Button
          variant={r ? 'outline' : 'default'}
          disabled={running}
          pending={start.isPending}
          onClick={() => start.mutate(!!r)}
        >
          {r ? 'Search again' : 'Research this topic'}
        </Button>
      </div>
      {!r && !latest.isPending && (
        <p className="text-sm text-muted-foreground">
          Checks what your materials already cover, searches the web for the gaps, and cross-checks key facts across
          sources.
        </p>
      )}
      {(latest.error || start.error) && (
        <p role="alert" className="text-sm text-destructive">{(latest.error ?? start.error)?.message}</p>
      )}
      {running && <JobProgress event={progress} label="Researching" />}
      {r?.status === 'failed' && (
        <p role="alert" className="text-sm text-destructive">
          {r.error}
        </p>
      )}
      {r?.status === 'succeeded' && <Results research={r} />}
    </section>
  )
}

function Results({ research: r }: { research: Research }) {
  const sources = useSources(r.id)
  const byId = new Map((sources.data ?? []).map((s) => [s.id, s]))
  return (
    <div className="grid gap-6">
      <div className="grid gap-2">
        <p className="text-sm">
          {r.sufficient
            ? 'Your materials cover this topic. These sources add explanations and examples.'
            : r.covered.length
              ? 'Your materials cover part of this topic. Searched for:'
              : "Your materials don't cover this topic yet. Searched for:"}
        </p>
        {r.missing.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {r.missing.map((m) => (
              <li key={m}>
                <Badge variant="outline" className="h-auto whitespace-normal text-left">
                  {m}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>

      {r.claims.length > 0 && (
        <div className="grid gap-2">
          <h3 className="font-medium">Key facts, cross-checked</h3>
          <ul className="grid gap-2">
            {r.claims.map((c) => (
              <li key={c.claim} className="grid gap-1 rounded-xl border p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm">{c.claim}</p>
                  <Badge variant={CLAIM_BADGE[c.status].variant} className="shrink-0">
                    {CLAIM_BADGE[c.status].label}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {[
                    ...c.sources.map((sid) => byId.get(sid)?.domain).filter(Boolean),
                    ...(c.materials.length ? ['your materials'] : []),
                  ].join(' · ')}
                  {c.contradicting.length > 0 &&
                    ` · contradicted by ${c.contradicting.map((sid) => byId.get(sid)?.domain).filter(Boolean).join(', ')}`}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-2">
        <h3 className="font-medium">Sources ({r.source_count})</h3>
        {sources.error && <p role="alert" className="text-sm text-destructive">{sources.error.message}</p>}
        <ul className="grid gap-2">
          {sources.data?.map((s) => (
            <SourceItem key={s.id} source={s} />
          ))}
        </ul>
      </div>
      <p className="text-xs text-muted-foreground">
        Searched: {r.queries.join(' · ')}
        {r.model && ` · ${r.model}`} · {new Date(r.created_at).toLocaleString()}
      </p>
    </div>
  )
}

function SourceItem({ source: s }: { source: Source }) {
  return (
    <li className="grid gap-1.5 rounded-xl border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="grid min-w-0 gap-0.5">
          {/* External link: never trusted, never rendered as HTML (PRD E6, rule 17) */}
          <a href={s.url} target="_blank" rel="noopener noreferrer nofollow" className="truncate font-medium hover:underline">
            {s.title}
          </a>
          <p className="text-xs text-muted-foreground">
            {s.domain} · {SOURCE_TYPE[s.source_type] ?? s.source_type} · quality {Math.round(s.quality * 100)}%
            {s.content_kind === 'snippet' && ' · search excerpt only'}
          </p>
        </div>
        <Badge variant={CLAIM_BADGE[s.verification_status].variant} className="shrink-0">
          {CLAIM_BADGE[s.verification_status].label}
        </Badge>
      </div>
      {s.passages.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">Relevant passages ({s.passages.length})</summary>
          <div className="mt-2 grid gap-2">
            {s.passages.map((p, i) => (
              <blockquote key={i} className="border-l-2 pl-3 text-muted-foreground">
                {p}
              </blockquote>
            ))}
          </div>
        </details>
      )}
    </li>
  )
}
