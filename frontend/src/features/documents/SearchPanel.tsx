import { useId } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useSearch } from '@/features/documents/api'
import { PassageCard } from '@/features/documents/PassageCard'

export function SearchPanel({ workspaceId, courseId }: { workspaceId: string; courseId?: string }) {
  const id = useId()
  const search = useSearch(workspaceId)

  return (
    <section className="grid gap-4" aria-labelledby={`${id}heading`}>
      <h2 id={`${id}heading`} className="text-lg font-medium">
        Search your materials
      </h2>
      <form
        role="search"
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const query = (new FormData(e.currentTarget).get('query') as string).trim()
          if (query) search.mutate({ query, course_id: courseId })
        }}
      >
        <Input name="query" aria-label="Search query" placeholder="e.g. which module covers deadlocks?" required />
        <Button type="submit" disabled={search.isPending}>
          {search.isPending ? 'Searching…' : 'Search'}
        </Button>
      </form>
      {search.error && <p role="alert" className="text-destructive">{search.error.message}</p>}
      {search.data?.length === 0 && <p className="text-muted-foreground">Nothing relevant found in the uploaded materials.</p>}
      {!!search.data?.length && (
        <ol className="grid gap-3">
          {search.data.map((p) => (
            <PassageCard key={p.chunk_id} passage={p} />
          ))}
        </ol>
      )}
    </section>
  )
}
