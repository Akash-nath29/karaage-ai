import type { Person } from '@/features/auth/api'

/** Profile picture, or initials when there's none. */
export function Avatar({ person, size = 28 }: { person: Pick<Person, 'display_name' | 'avatar_url'>; size?: number }) {
  const style = { width: size, height: size }
  if (person.avatar_url) return <img src={person.avatar_url} alt="" style={style} className="shrink-0 rounded-full object-cover" />
  const initials = person.display_name.split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase()
  return (
    <span aria-hidden style={{ ...style, fontSize: size * 0.4 }}
          className="inline-flex shrink-0 items-center justify-center rounded-full bg-muted font-medium text-muted-foreground">
      {initials}
    </span>
  )
}
