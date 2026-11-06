import 'katex/dist/katex.min.css'

import ReactMarkdown, { type Components } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

import { cn } from '@/lib/utils'

// LLM-written text: no raw HTML (react-markdown drops it; no rehype-raw), unsafe URLs stripped by its default
// urlTransform, KaTeX with trust off (PRD rule 17). Same KaTeX options the backend validates with.
const rehypePlugins = [[rehypeKatex, { throwOnError: false, trust: false, strict: 'ignore' }]] as const
const remarkPlugins = [remarkGfm, remarkMath]

const links: Components = {
  a: ({ href, children }) =>
    href?.startsWith('#') ? ( // in-page reference, e.g. a tutor citation marker
      <a href={href} className="text-xs font-medium text-muted-foreground no-underline hover:text-foreground">
        {children}
      </a>
    ) : (
      <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="underline underline-offset-2">
        {children}
      </a>
    ),
}
const inlineOnly: Components = { ...links, p: ({ children }) => <>{children}</> }

/** Markdown with math. `inline` drops the paragraph wrapper (table cells, list items, quiz options). */
export function Markdown({ text, inline, className }: { text: string; inline?: boolean; className?: string }) {
  const content = (
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- rehype plugin tuple typing
    <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins as any} components={inline ? inlineOnly : links}>
      {text}
    </ReactMarkdown>
  )
  return inline ? content : <div className={cn('md', className)}>{content}</div>
}
