import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { Avatar } from '@/components/avatar'
import { SimpleForm } from '@/components/simple-form'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useDeleteAccount, useMe, useRemoveAvatar, useSetAvatar, useUpdateProfile } from '@/features/auth/api'
import { api } from '@/lib/api'

type MyUsage = {
  month_start: string
  tokens: number
  token_budget: number
  searches: number
  by_workspace: { workspace_id: string; name: string; tokens: number }[]
}

const PROFILE_FIELDS = [
  { name: 'display_name', label: 'Name', required: true },
  { name: 'preferred_language', label: 'Preferred language', hint: 'The tutor answers in it.' },
  { name: 'academic_level', label: 'Academic level', hint: 'For example "B.Tech, 3rd year".' },
  { name: 'learning_preferences', label: 'How you like to learn', multiline: true,
    hint: 'For example "short answers, lots of worked examples". The tutor takes it into account.' },
]

/** A3 profile, your AI usage this month (§12.6), and deleting your account (§10.5). */
export function ProfilePage() {
  const me = useMe()
  const update = useUpdateProfile()
  const [saved, setSaved] = useState(false)
  if (!me.data) return null
  const u = me.data
  return (
    <div className="grid max-w-xl gap-10">
      <section className="grid gap-4">
        <h1 className="text-2xl font-semibold">Your profile</h1>
        <p className="text-sm text-muted-foreground">
          {u.email} · {u.email_verified ? 'email confirmed' : 'email not confirmed yet'}
        </p>
        <AvatarEditor />
        <SimpleForm
          key={u.display_name + u.preferred_language + u.academic_level + u.learning_preferences}
          fields={PROFILE_FIELDS}
          initial={{ display_name: u.display_name, preferred_language: u.preferred_language, academic_level: u.academic_level,
                     learning_preferences: u.learning_preferences }}
          submitLabel="Save profile"
          pending={update.isPending}
          error={update.error}
          onSubmit={async (v) => {
            setSaved(false)
            await update.mutateAsync(v)
            setSaved(true)
          }}
        />
        {saved && <p role="status" className="text-sm text-muted-foreground">Saved.</p>}
      </section>
      <Usage />
      <DeleteAccount />
    </div>
  )
}

function AvatarEditor() {
  const me = useMe()
  const set = useSetAvatar()
  const remove = useRemoveAvatar()
  if (!me.data) return null
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Avatar person={me.data} size={64} />
      <div className="grid gap-1.5">
        <Label htmlFor="avatar">Profile picture (PNG or JPEG, up to 2 MB)</Label>
        <div className="flex gap-2">
          <Input id="avatar" type="file" accept="image/png,image/jpeg" disabled={set.isPending}
                 onChange={(e) => e.target.files?.[0] && set.mutate(e.target.files[0], { onSettled: () => (e.target.value = '') })} />
          {me.data.avatar_url && (
            <Button variant="ghost" pending={remove.isPending} onClick={() => remove.mutate()}>
              Remove
            </Button>
          )}
        </div>
        {(set.error ?? remove.error) && <p role="alert" className="text-sm text-destructive">{(set.error ?? remove.error)?.message}</p>}
      </div>
    </div>
  )
}

function Usage() {
  const usage = useQuery({ queryKey: ['usage', 'me'], queryFn: () => api<MyUsage>('/users/me/usage') })
  const u = usage.data
  if (!u) return null
  const share = u.token_budget ? Math.min(1, u.tokens / u.token_budget) : 0
  return (
    <section className="grid gap-3" aria-labelledby="usage-title">
      <h2 id="usage-title" className="text-lg font-medium">Your AI usage this month</h2>
      <p className="text-sm">
        {u.tokens.toLocaleString()} {u.token_budget ? `of ${u.token_budget.toLocaleString()} ` : ''}tokens · {u.searches} web searches
      </p>
      {u.token_budget > 0 && (
        <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Monthly AI allowance used"
             aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share * 100)}>
          <div className="h-full bg-primary" style={{ width: `${share * 100}%` }} />
        </div>
      )}
      {u.by_workspace.length > 0 && (
        <ul className="grid gap-0.5 text-sm text-muted-foreground">
          {u.by_workspace.map((w) => (
            <li key={w.workspace_id}>{w.name}: {w.tokens.toLocaleString()} tokens</li>
          ))}
        </ul>
      )}
    </section>
  )
}

function DeleteAccount() {
  const remove = useDeleteAccount()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  return (
    <section className="grid gap-3 rounded-xl border border-destructive/30 p-4" aria-labelledby="delete-title">
      <h2 id="delete-title" className="font-medium">Delete your account</h2>
      <p className="text-sm text-muted-foreground">
        Deletes your account, your tutor conversations, quizzes and progress, and every workspace you own with everything in
        it. Workspaces you're a member of keep the documents and lessons you shared there. This can't be undone.
      </p>
      {open ? (
        <form
          className="grid gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            remove.mutate(new FormData(e.currentTarget).get('password') as string, { onSuccess: () => navigate('/register') })
          }}
        >
          <Label htmlFor="delete-password">Your password</Label>
          <Input id="delete-password" name="password" type="password" autoComplete="current-password" required />
          <div className="flex gap-2">
            <Button type="submit" variant="destructive" pending={remove.isPending}>Delete my account</Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
          {remove.error && <p role="alert" className="text-sm text-destructive">{remove.error.message}</p>}
        </form>
      ) : (
        <Button variant="destructive" className="justify-self-start" onClick={() => setOpen(true)}>
          Delete account…
        </Button>
      )}
    </section>
  )
}
