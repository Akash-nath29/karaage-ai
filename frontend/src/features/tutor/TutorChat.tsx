import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'

import { CitationLink } from '@/components/lesson-blocks/blocks'
import { Markdown } from '@/components/lesson-blocks/markdown'
import { NativeSelect } from '@/components/native-select'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { asCitation, askTutor, MODES, useMessages, type Mode, type TutorMessage } from '@/features/tutor/api'
import { cn } from '@/lib/utils'

// `count`: messages in the history when the question was asked. The saved question and answer replace the draft as
// soon as a refetch includes them (count + 1, count + 2), whenever that refetch happens.
type Draft = { question: string; answer: string; status: string; count: number }

/** A tutor conversation (PRD G1–G3): history, streamed answers with citations, follow-ups, mode and web search.
 * `ensureSession` creates the conversation on the first question when there isn't one yet (lesson panel). */
export function TutorChat({
  sessionId,
  ensureSession,
  onSession,
  initialMode = 'doubt',
  className,
}: {
  sessionId: string | null
  ensureSession?: () => Promise<string>
  onSession?: (id: string) => void
  initialMode?: Mode
  className?: string
}) {
  const id = useId()
  const qc = useQueryClient()
  const [created, setCreated] = useState<string | null>(null) // set once its first answer is saved
  const activeId = sessionId ?? created
  const messages = useMessages(activeId)
  const [mode, setMode] = useState<Mode>(initialMode)
  const [web, setWeb] = useState(false)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const list = messages.data ?? []

  useEffect(() => {
    const el = scroller.current
    if (el) el.scrollTop = el.scrollHeight
  }, [list.length, draft?.answer, draft?.question])

  async function ask(question: string) {
    if (!question.trim() || draft) return
    setError(null)
    setDraft({ question, answer: '', status: 'Starting…', count: list.length })
    const controller = new AbortController()
    abort.current = controller
    let target = activeId
    try {
      target ??= await ensureSession!()
      await askTutor(
        target,
        { content: question, mode, web },
        {
          onStatus: (status) => setDraft((d) => d && { ...d, status }),
          onToken: (text) => setDraft((d) => d && { ...d, answer: d.answer + text }),
          onError: setError,
          onDone: () => {},
        },
        controller.signal,
      )
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message)
    } finally {
      // ponytail: after "Stop" the server saves the partial answer as it notices the disconnect; give it a moment.
      if (controller.signal.aborted) await new Promise((r) => setTimeout(r, 600))
      abort.current = null
      if (target && !activeId) {
        setCreated(target)
        onSession?.(target)
      }
      if (target) {
        await qc.invalidateQueries({ queryKey: ['tutor-messages', target] })
        void qc.invalidateQueries({ queryKey: ['tutor-sessions'] })
        void qc.invalidateQueries({ queryKey: ['tutor-session', target] })
      }
      setDraft(null)
    }
  }

  const lastAssistant = list.findLast((m) => m.role === 'assistant')
  return (
    <div className={cn('grid gap-4', className)}>
      <div ref={scroller} className="max-h-[65vh] min-h-40 overflow-y-auto rounded-xl border p-4">
        {list.length === 0 && !draft ? (
          <p className="text-sm text-muted-foreground">
            Ask anything about the topic. Answers use your course materials first and cite them.
          </p>
        ) : (
          <ol aria-label="Conversation" className="grid gap-5">
            {list.map((m) =>
              m.role === 'user' ? (
                <UserMessage key={m.id} text={m.content} />
              ) : (
                <AssistantMessage key={m.id} message={m} onAsk={m === lastAssistant && !draft ? ask : undefined} />
              ),
            )}
            {draft && list.length < draft.count + 2 && (
              <>
                {list.length === draft.count && <UserMessage text={draft.question} />}
                <li className="grid gap-1" aria-busy="true">
                  <p className="text-xs text-muted-foreground" aria-live="polite">
                    {draft.status}
                  </p>
                  {draft.answer && <Markdown text={draft.answer} />}
                </li>
              </>
            )}
          </ol>
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <form
        className="grid gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const form = e.currentTarget
          const text = (new FormData(form).get('question') as string).trim()
          if (text) {
            form.reset()
            void ask(text)
          }
        }}
      >
        <Label htmlFor={`${id}q`} className="sr-only">
          Your question
        </Label>
        <Textarea
          id={`${id}q`}
          name="question"
          required
          maxLength={4000}
          rows={2}
          placeholder="Ask a question… (Enter to send, Shift+Enter for a new line)"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              e.currentTarget.form?.requestSubmit()
            }
          }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Label htmlFor={`${id}mode`} className="text-sm">
            Mode
          </Label>
          <NativeSelect id={`${id}mode`} value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}: {m.hint}
              </option>
            ))}
          </NativeSelect>
          <label className="flex items-center gap-1.5 text-sm">
            <input type="checkbox" checked={web} onChange={(e) => setWeb(e.target.checked)} />
            Also search the web
          </label>
          <div className="ml-auto flex gap-2">
            {draft ? (
              <Button type="button" variant="outline" onClick={() => abort.current?.abort()}>
                Stop
              </Button>
            ) : (
              <Button type="submit">Ask</Button>
            )}
          </div>
        </div>
      </form>
    </div>
  )
}

function UserMessage({ text }: { text: string }) {
  return (
    <li className="ml-auto max-w-[85%] rounded-2xl bg-muted px-4 py-2 whitespace-pre-wrap">
      <span className="sr-only">You: </span>
      {text}
    </li>
  )
}

function AssistantMessage({ message: m, onAsk }: { message: TutorMessage; onAsk?: (q: string) => void }) {
  const labels = new Set(m.citations.map((c) => c.label))
  // [M1] markers become links to this answer's source list
  const text = m.content.replace(/\[([MW]\d+)\]/g, (marker, label) => (labels.has(label) ? `[[${label}]](#cite-${m.id}-${label})` : marker))
  return (
    <li className="grid gap-2">
      <span className="sr-only">Tutor: </span>
      {m.content ? <Markdown text={text} /> : null}
      {m.status === 'interrupted' && <p className="text-xs text-muted-foreground">Stopped before the end.</p>}
      {m.status === 'error' && (
        <p className="text-xs text-destructive">This answer failed{m.content ? ' partway' : ''}. Ask again to retry.</p>
      )}
      {m.citations.length > 0 && (
        <div className="grid gap-1 text-xs">
          <p className="font-medium text-muted-foreground">Sources</p>
          <ol className="grid gap-1">
            {m.citations.map((c) => (
              <li key={c.label} id={`cite-${m.id}-${c.label}`} className="scroll-mt-4">
                <span className="font-mono text-muted-foreground">[{c.label}]</span> <CitationLink citation={asCitation(c)} />
                {c.kind === 'web' && c.title && <span className="text-muted-foreground"> · {c.title}</span>}
                <details>
                  <summary className="cursor-pointer text-muted-foreground">What the tutor used</summary>
                  <blockquote className="mt-1 border-l-2 pl-3 whitespace-pre-line text-muted-foreground">{c.quote}</blockquote>
                </details>
              </li>
            ))}
          </ol>
        </div>
      )}
      {m.content && m.citations.length === 0 && m.status === 'complete' && (
        <p className="text-xs text-muted-foreground">No sources cited: written by the AI from general knowledge.</p>
      )}
      {onAsk && m.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2" aria-label="Suggested follow-up questions">
          {m.suggestions.map((s) => (
            <Button key={s} type="button" size="sm" variant="outline" className="h-auto py-1 text-left whitespace-normal" onClick={() => onAsk(s)}>
              {s}
            </Button>
          ))}
        </div>
      )}
    </li>
  )
}
