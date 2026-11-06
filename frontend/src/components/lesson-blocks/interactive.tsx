import { useId, useState } from 'react'

import { Markdown } from '@/components/lesson-blocks/markdown'
import { Button } from '@/components/ui/button'
import type { Block } from '@/features/lessons/api'
import { cn } from '@/lib/utils'

type QuizBlock = Extract<Block, { type: 'quiz' }>
type FlashcardsBlock = Extract<Block, { type: 'flashcards' }>

/** Self-check MCQs (graded in the browser; saved attempts and progress come with assessments, Phase 5). */
export function Quiz({ block }: { block: QuizBlock }) {
  return (
    <ol className="grid gap-4">
      {block.questions.map((q, i) => (
        <QuizQuestion key={i} number={i + 1} question={q} />
      ))}
    </ol>
  )
}

function QuizQuestion({ number, question: q }: { number: number; question: QuizBlock['questions'][number] }) {
  const name = useId()
  const [chosen, setChosen] = useState<number | null>(null)
  const [checked, setChecked] = useState(false)
  return (
    <li className="grid gap-2">
      <fieldset className="grid gap-2">
        <legend className="mb-1 font-medium">
          {number}. <Markdown text={q.question} inline />
        </legend>
        {q.options.map((option, i) => (
          <label
            key={i}
            className={cn(
              'flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm',
              checked && i === q.answer && 'border-green-600 bg-green-50 dark:bg-green-950',
              checked && i === chosen && i !== q.answer && 'border-destructive bg-destructive/10',
            )}
          >
            <input
              type="radio"
              name={name}
              className="mt-1"
              checked={chosen === i}
              onChange={() => {
                setChosen(i)
                setChecked(false)
              }}
            />
            <span>
              <Markdown text={option} inline />
            </span>
          </label>
        ))}
      </fieldset>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" size="sm" variant="outline" disabled={chosen === null} onClick={() => setChecked(true)}>
          Check answer
        </Button>
        {checked && (
          <p role="status" className={cn('text-sm font-medium', chosen === q.answer ? 'text-green-700' : 'text-destructive')}>
            {chosen === q.answer ? 'Correct' : 'Not quite'}
          </p>
        )}
      </div>
      {checked && q.explanation && <Markdown text={q.explanation} className="text-sm text-muted-foreground" />}
    </li>
  )
}

export function Flashcards({ block }: { block: FlashcardsBlock }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {block.cards.map((card, i) => (
        <Flashcard key={i} card={card} />
      ))}
    </ul>
  )
}

function Flashcard({ card }: { card: FlashcardsBlock['cards'][number] }) {
  const [flipped, setFlipped] = useState(false)
  return (
    <li>
      <button
        type="button"
        aria-pressed={flipped}
        onClick={() => setFlipped((f) => !f)}
        className="grid min-h-24 w-full content-center gap-1 rounded-xl border p-4 text-left text-sm transition-colors hover:bg-muted/50"
      >
        <span className="text-xs text-muted-foreground">{flipped ? 'Answer' : 'Question'} · tap to flip</span>
        <Markdown text={flipped ? card.back : card.front} inline />
      </button>
    </li>
  )
}
