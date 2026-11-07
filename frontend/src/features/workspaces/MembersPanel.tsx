import { useState } from 'react'
import { useNavigate } from 'react-router'

import { Avatar } from '@/components/avatar'
import { NativeSelect } from '@/components/native-select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useMe } from '@/features/auth/api'
import {
  useAudit,
  useChangeRole,
  useInvitations,
  useInvite,
  useMembers,
  useRemoveMember,
  useRevokeInvitation,
  type AuditEntry,
  type InvitationCreated,
  type InviteRole,
} from '@/features/workspaces/api'
import { atLeast, type Role } from '@/lib/api'

const ROLE_HELP: Record<InviteRole, string> = {
  viewer: 'reads shared material, uses the tutor and quizzes',
  editor: 'also uploads documents, generates and shares lessons, edits the question bank',
  admin: 'also manages courses, the syllabus and members',
}

/** A11: admins manage editors and viewers; only the owner manages admins; the owner's role never changes. */
const manageable = (mine: Role, theirs: Role) => theirs !== 'owner' && atLeast(mine, theirs === 'admin' ? 'owner' : 'admin')
const assignable = (mine: Role): InviteRole[] => (mine === 'owner' ? ['viewer', 'editor', 'admin'] : ['viewer', 'editor'])
const when = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })

export function MembersPanel({ workspaceId, role }: { workspaceId: string; role: Role }) {
  const me = useMe()
  const members = useMembers(workspaceId)
  const changeRole = useChangeRole(workspaceId)
  const remove = useRemoveMember(workspaceId)
  const navigate = useNavigate()
  const isAdmin = atLeast(role, 'admin')

  return (
    <section className="grid gap-4" aria-labelledby="members-heading">
      <h2 id="members-heading" className="text-lg font-medium">Members</h2>
      {members.error && <p role="alert" className="text-destructive">{members.error.message}</p>}
      <ul className="grid gap-2">
        {members.data?.map((m) => {
          const self = m.user.id === me.data?.id
          return (
            <li key={m.user.id} className="flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2">
              <Avatar person={m.user} />
              <div className="grid min-w-0 flex-1">
                <span className="truncate font-medium">{m.user.display_name}{self && ' (you)'}</span>
                <span className="truncate text-xs text-muted-foreground">{m.user.email}</span>
              </div>
              {!self && manageable(role, m.role) ? (
                <>
                  <NativeSelect aria-label={`Role of ${m.user.display_name}`} value={m.role} disabled={changeRole.isPending}
                                onChange={(e) => changeRole.mutate({ userId: m.user.id, role: e.target.value as InviteRole })}>
                    {[...new Set([...assignable(role), m.role])].map((r) => <option key={r} value={r}>{r}</option>)}
                  </NativeSelect>
                  <Button variant="ghost" size="sm" disabled={remove.isPending} pending={remove.isPending && remove.variables === m.user.id}
                          onClick={() => remove.mutate(m.user.id)}>
                    Remove
                  </Button>
                </>
              ) : (
                <Badge variant={m.role === 'owner' ? 'default' : 'secondary'}>{m.role}</Badge>
              )}
              {self && m.role !== 'owner' && (
                <Button variant="ghost" size="sm" pending={remove.isPending}
                        onClick={() => remove.mutate(m.user.id, { onSuccess: () => navigate('/') })}>
                  Leave
                </Button>
              )}
            </li>
          )
        })}
      </ul>
      {(changeRole.error || remove.error) && (
        <p role="alert" className="text-sm text-destructive">{(changeRole.error ?? remove.error)?.message}</p>
      )}
      {isAdmin && <InvitePanel workspaceId={workspaceId} role={role} />}
      {isAdmin && <Activity workspaceId={workspaceId} />}
    </section>
  )
}

function InvitePanel({ workspaceId, role }: { workspaceId: string; role: Role }) {
  const invite = useInvite(workspaceId)
  const invitations = useInvitations(workspaceId, true)
  const revoke = useRevokeInvitation(workspaceId)
  const [created, setCreated] = useState<InvitationCreated | null>(null)
  const [inviteRole, setInviteRole] = useState<InviteRole>('viewer')
  const [copied, setCopied] = useState(false)

  return (
    <div className="grid gap-3 rounded-lg border p-4">
      <h3 className="font-medium">Invite people</h3>
      <form
        className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end"
        onSubmit={async (e) => {
          e.preventDefault()
          const form = e.currentTarget
          const email = (new FormData(form).get('email') as string).trim()
          setCopied(false)
          setCreated(await invite.mutateAsync({ email: email || null, role: inviteRole }).catch(() => null))
          form.reset()
        }}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="invite-email">Email (leave empty for a link anyone can use)</Label>
          <Input id="invite-email" name="email" type="email" placeholder="classmate@example.com" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="invite-role">Role</Label>
          <NativeSelect id="invite-role" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as InviteRole)}>
            {assignable(role).map((r) => <option key={r} value={r}>{r}</option>)}
          </NativeSelect>
        </div>
        <Button type="submit" pending={invite.isPending}>Invite</Button>
      </form>
      <p className="text-xs text-muted-foreground">A {inviteRole} {ROLE_HELP[inviteRole]}. Invitations expire after 7 days.</p>
      {invite.error && <p role="alert" className="text-sm text-destructive">{invite.error.message}</p>}
      {created && (
        <div role="status" className="grid gap-2 rounded-md bg-muted/50 p-3 text-sm">
          <p>
            {created.email
              ? created.emailed ? `Invitation emailed to ${created.email}.` : `Couldn't send the email to ${created.email}; share the link instead.`
              : 'Share this link. It works until it expires or you revoke it.'}{' '}
            The link is shown only once.
          </p>
          <div className="flex gap-2">
            <Input readOnly value={created.url} aria-label="Invitation link" onFocus={(e) => e.currentTarget.select()} />
            <Button type="button" variant="outline"
                    onClick={() => navigator.clipboard.writeText(created.url).then(() => setCopied(true))}>
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
        </div>
      )}
      {!!invitations.data?.length && (
        <div className="grid gap-2">
          <h4 className="text-sm font-medium">Open invitations</h4>
          <ul className="grid gap-1 text-sm">
            {invitations.data.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center gap-2">
                <span>{i.email ?? 'Link'}</span>
                <Badge variant="secondary">{i.role}</Badge>
                <span className="text-muted-foreground">
                  {i.email ? '' : `${i.uses}${i.max_uses ? `/${i.max_uses}` : ''} joined · `}expires {when(i.expires_at)}
                </span>
                {atLeast(role, i.role === 'admin' ? 'owner' : 'admin') && (
                  <Button variant="ghost" size="sm" disabled={revoke.isPending} pending={revoke.isPending && revoke.variables === i.id} onClick={() => revoke.mutate(i.id)}>
                    Revoke
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/** One audit entry as a sentence fragment after the actor's name. */
function describe(a: AuditEntry): string {
  const target = a.target === 'link' ? 'an invitation link' : a.target
  const role = a.details.role ? ` (${a.details.role})` : ''
  switch (a.action) {
    case 'workspace.created': return 'created the workspace'
    case 'member.joined': return `joined as ${a.details.role}`
    case 'member.left': return 'left'
    case 'member.removed': return `removed ${target}`
    case 'member.role_changed': return `changed ${target} from ${a.details.old} to ${a.details.new}`
    case 'invitation.created': return a.target === 'link' ? `created an invitation link${role}` : `invited ${target}${role}`
    case 'invitation.revoked': return `revoked ${a.target === 'link' ? 'an invitation link' : `the invitation for ${target}`}`
    case 'document.deleted': return `deleted ${target}`
    case 'course.deleted': return `deleted the course ${target}`
    case 'lesson.published': return `shared the lesson on ${target}`
    default: return `${a.action} ${target}`
  }
}

/** Audit log (PRD §10.4), newest first: admins and the owner only. */
function Activity({ workspaceId }: { workspaceId: string }) {
  const audit = useAudit(workspaceId, true)
  const [all, setAll] = useState(false)
  if (!audit.data?.length) return null
  const shown = all ? audit.data : audit.data.slice(0, 8)
  return (
    <div className="grid gap-2">
      <h3 className="font-medium">Recent activity</h3>
      <ul className="grid gap-1 text-sm">
        {shown.map((a, i) => (
          <li key={i} className="text-muted-foreground">
            <span className="text-foreground">{a.actor ?? 'Someone'}</span> {describe(a)} · {when(a.created_at)}
          </li>
        ))}
      </ul>
      {audit.data.length > shown.length && (
        <Button variant="ghost" size="sm" className="justify-self-start" onClick={() => setAll(true)}>
          Show all
        </Button>
      )}
    </div>
  )
}
