import { useEffect, useId, useState } from 'react'

type Mermaid = typeof import('mermaid').default
let loading: Promise<Mermaid> | null = null

// Mermaid is large: load it only when a lesson actually has a diagram.
function loadMermaid(): Promise<Mermaid> {
  loading ??= import('mermaid').then(({ default: mermaid }) => {
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral' })
    return mermaid
  })
  return loading
}

/** Renders Mermaid source compiled by the backend (valid by construction, D15). Shows the source if it fails. */
export function MermaidDiagram({ source, label }: { source: string; label: string }) {
  const id = `mermaid-${useId().replace(/[^a-zA-Z0-9]/g, '')}`
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    loadMermaid()
      .then((mermaid) => mermaid.render(id, source))
      .then(({ svg }) => alive && setSvg(svg))
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      alive = false
    }
  }, [id, source])

  if (error)
    return (
      <div role="alert" className="grid gap-1 text-sm">
        <p className="text-destructive">This diagram couldn't be drawn. Its source:</p>
        <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">{source}</pre>
      </div>
    )
  if (!svg) return <p className="text-sm text-muted-foreground">Drawing diagram…</p>
  // SVG from Mermaid's strict mode (sanitized by Mermaid); labels were escaped when the source was compiled.
  return (
    <div
      role="img"
      aria-label={label}
      className="diagram overflow-x-auto [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
