// Self-check for the next-stop rule: node --experimental-strip-types src/features/courses/journey.check.ts
import assert from 'node:assert/strict'

import { nextStop, stations, stopPath } from './journey.ts'

const topic = (id: string, ready = true) => ({ id, title: id, status: ready ? 'lesson_available' : 'generation_pending' })
const structure = { units: [{ id: 'u1', title: 'Unit 1', topics: [topic('a'), topic('b'), topic('c', false), topic('d')] }] } as never
const progress = (states: Record<string, string>) =>
  ({ topics: Object.entries(states).map(([topic_id, status]) => ({ topic_id, status, last_accuracy: null })) }) as never
const stop = (states: Record<string, string>) => nextStop(stations(structure, progress(states)))

assert.equal(stop({})?.station.id, 'a', 'fresh course: the first topic')
assert.equal(stop({ a: 'completed' })?.station.id, 'b', 'then the next topic in order')
assert.equal(stop({ a: 'completed', b: 'completed' })?.station.id, 'd', 'skips a topic whose lesson is still being written')
assert.equal(stop({ a: 'completed', b: 'completed', d: 'completed' })?.station.id, 'c', '...but comes back to it')
assert.equal(stop({ a: 'completed', b: 'revision_required' })?.action, 'revise', 'a weak topic comes before a new one')
const reading = stop({ a: 'revision_required', b: 'studied' })!
assert.deepEqual([reading.station.id, reading.action, stopPath(reading)], ['b', 'check', '/topics/b/check'], 'a topic read but not checked comes first')
assert.equal(stop({ a: 'completed', b: 'completed', c: 'completed', d: 'completed' }), null, 'nothing left: no next stop')
assert.equal(stations(structure)[0].state, 'todo', 'no progress yet: every station is to learn')
console.log('journey: all checks passed')
