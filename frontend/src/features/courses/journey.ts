import type { CourseProgress, ProgressStatus } from '@/features/assessments/api'
import type { StructureOut } from '@/features/syllabus/api'

/** Where a learner stands on one topic, drawn as a station on its unit's line (D38). */
export type StationState = 'done' | 'revise' | 'studied' | 'todo'

export type Station = {
  id: string
  title: string
  unitId: string
  unitTitle: string
  state: StationState
  lessonReady: boolean
  lastAccuracy: number | null
}

const STATE: Record<ProgressStatus, StationState> = {
  completed: 'done',
  revision_required: 'revise',
  studied: 'studied',
  not_started: 'todo',
}

/** Every topic in syllabus order, with this learner's state on it. */
export function stations(structure: Pick<StructureOut, 'units'>, progress?: Pick<CourseProgress, 'topics'>): Station[] {
  const mine = new Map(progress?.topics.map((t) => [t.topic_id, t]))
  return structure.units.flatMap((u) =>
    u.topics.map((t) => {
      const p = mine.get(t.id)
      return {
        id: t.id,
        title: t.title,
        unitId: u.id,
        unitTitle: u.title,
        state: p ? STATE[p.status] : 'todo',
        lessonReady: t.status === 'lesson_available',
        lastAccuracy: p?.last_accuracy ?? null,
      }
    }),
  )
}

export type NextStop = { station: Station; action: 'check' | 'revise' | 'learn' }

/** The one thing to do next: finish a topic you've read but not checked, then revise a weak one, then the next new
 * topic in syllabus order (one whose lesson is ready before one still being written). Null once everything is done. */
export function nextStop(list: Station[]): NextStop | null {
  const unchecked = list.find((s) => s.state === 'studied')
  if (unchecked) return { station: unchecked, action: 'check' }
  const weak = list.find((s) => s.state === 'revise')
  if (weak) return { station: weak, action: 'revise' }
  const next = list.find((s) => s.state === 'todo' && s.lessonReady) ?? list.find((s) => s.state === 'todo')
  return next ? { station: next, action: 'learn' } : null
}

/** Where a next-stop link goes: straight to the check for a topic already read, otherwise to the lesson. */
export const stopPath = ({ station, action }: NextStop) => `/topics/${station.id}${action === 'check' ? '/check' : ''}`

/** The label of the button that takes you to a next stop. */
export const STOP_ACTION: Record<NextStop['action'], string> = { check: 'Check yourself', revise: 'Revise it', learn: 'Start' }
