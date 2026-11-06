import { ArrowDown, ArrowUp, Plus, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Structure } from '@/features/syllabus/api'

// Editor rows carry a client `key` so React keeps each input's identity across reorders; ids go back to the API.
type Sub = { key: string; id?: string | null; title: string }
type Top = { key: string; id?: string | null; title: string; subtopics: Sub[] }
type Un = { key: string; id?: string | null; title: string; hours: number | null; topics: Top[] }

const newKey = () => crypto.randomUUID()

const withKeys = (s: Structure): Un[] =>
  s.units.map((u) => ({
    ...u,
    key: newKey(),
    topics: u.topics.map((t) => ({ ...t, key: newKey(), subtopics: t.subtopics.map((st) => ({ ...st, key: newKey() })) })),
  }))

const withoutKeys = (units: Un[]): Structure => ({
  units: units.map(({ key: _u, topics, ...u }) => ({
    ...u,
    topics: topics.map(({ key: _t, subtopics, ...t }) => ({ ...t, subtopics: subtopics.map(({ key: _s, ...s }) => s) })),
  })),
})

function move<T>(list: T[], i: number, by: number) {
  const j = i + by
  if (j >= 0 && j < list.length) [list[i], list[j]] = [list[j], list[i]]
}

function RowActions({ what, onMove, onRemove }: { what: string; onMove: (by: number) => void; onRemove: () => void }) {
  return (
    <div className="flex shrink-0">
      <Button type="button" variant="ghost" size="icon-sm" aria-label={`Move ${what} up`} onClick={() => onMove(-1)}>
        <ArrowUp />
      </Button>
      <Button type="button" variant="ghost" size="icon-sm" aria-label={`Move ${what} down`} onClick={() => onMove(1)}>
        <ArrowDown />
      </Button>
      <Button type="button" variant="ghost" size="icon-sm" aria-label={`Remove ${what}`} onClick={onRemove}>
        <X />
      </Button>
    </div>
  )
}

type Action = { action: string; label: string; variant?: 'default' | 'outline' }

type Props = {
  initial: Structure
  actions: Action[] // submit buttons; the clicked one's `action` is passed to onSave
  onSave: (structure: Structure, action: string) => Promise<unknown>
  pending?: boolean
  error?: Error | null
  children?: ReactNode // extra buttons (e.g. Cancel)
}

export function StructureEditor({ initial, actions, onSave, pending, error, children }: Props) {
  const [units, setUnits] = useState(() => withKeys(initial))
  const edit = (change: (draft: Un[]) => void) =>
    setUnits((current) => {
      const next = structuredClone(current)
      change(next)
      return next
    })

  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        const submitter = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null
        onSave(withoutKeys(units), submitter?.value ?? actions[0].action).catch(() => {}) // error shown via prop
      }}
    >
      {units.map((u, ui) => (
        <fieldset key={u.key} className="grid gap-3 rounded-xl border p-4">
          <legend className="sr-only">Unit {ui + 1}</legend>
          <div className="flex items-center gap-2">
            <span className="w-12 shrink-0 text-sm text-muted-foreground">Unit {ui + 1}</span>
            <Input
              aria-label={`Unit ${ui + 1} title`}
              required
              value={u.title}
              onChange={(e) => edit((d) => void (d[ui].title = e.target.value))}
            />
            <Input
              aria-label={`Unit ${ui + 1} lecture hours`}
              type="number"
              min={0}
              max={500}
              placeholder="hours"
              className="w-24"
              value={u.hours ?? ''}
              onChange={(e) => edit((d) => void (d[ui].hours = e.target.value === '' ? null : Number(e.target.value)))}
            />
            <RowActions what={`unit ${ui + 1}`} onMove={(by) => edit((d) => move(d, ui, by))} onRemove={() => edit((d) => void d.splice(ui, 1))} />
          </div>
          <ol className="grid gap-3 sm:pl-14">
            {u.topics.map((t, ti) => (
              <li key={t.key} className="grid gap-1.5">
                <div className="flex items-center gap-2">
                  <Input
                    aria-label={`Unit ${ui + 1}, topic ${ti + 1}`}
                    required
                    value={t.title}
                    onChange={(e) => edit((d) => void (d[ui].topics[ti].title = e.target.value))}
                  />
                  <RowActions
                    what={`topic ${ti + 1} of unit ${ui + 1}`}
                    onMove={(by) => edit((d) => move(d[ui].topics, ti, by))}
                    onRemove={() => edit((d) => void d[ui].topics.splice(ti, 1))}
                  />
                </div>
                <ul className="grid gap-1.5 pl-6">
                  {t.subtopics.map((s, si) => (
                    <li key={s.key} className="flex items-center gap-2">
                      <Input
                        aria-label={`Subtopic ${si + 1} of ${t.title || `topic ${ti + 1}`}`}
                        required
                        className="h-7 text-sm"
                        value={s.title}
                        onChange={(e) => edit((d) => void (d[ui].topics[ti].subtopics[si].title = e.target.value))}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        aria-label={`Remove subtopic ${s.title || si + 1}`}
                        onClick={() => edit((d) => void d[ui].topics[ti].subtopics.splice(si, 1))}
                      >
                        <X />
                      </Button>
                    </li>
                  ))}
                  <li>
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      onClick={() => edit((d) => void d[ui].topics[ti].subtopics.push({ key: newKey(), title: '' }))}
                    >
                      <Plus /> Subtopic
                    </Button>
                  </li>
                </ul>
              </li>
            ))}
          </ol>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="justify-self-start sm:ml-14"
            onClick={() => edit((d) => void d[ui].topics.push({ key: newKey(), title: '', subtopics: [] }))}
          >
            <Plus /> Topic
          </Button>
        </fieldset>
      ))}
      <Button
        type="button"
        variant="outline"
        className="justify-self-start"
        onClick={() => edit((d) => void d.push({ key: newKey(), title: '', hours: null, topics: [] }))}
      >
        <Plus /> Unit
      </Button>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error.message}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <Button key={a.action} type="submit" name="action" value={a.action} variant={a.variant ?? 'default'} disabled={pending}>
            {a.label}
          </Button>
        ))}
        {children}
      </div>
    </form>
  )
}
