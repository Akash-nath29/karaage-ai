import { Eye, EyeOff } from 'lucide-react'
import { useId, useState, type ComponentProps } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

export type Field = {
  name: string
  label: string
  required?: boolean
  multiline?: boolean
  type?: 'text' | 'email' | 'password'
  autoComplete?: string
  minLength?: number
  hint?: string
}

type Props = {
  fields: Field[]
  initial?: Record<string, string>
  submitLabel: string
  pending?: boolean
  error?: Error | null
  onSubmit: (values: Record<string, string>) => Promise<unknown>
  onCancel?: () => void
}

// Uncontrolled form: the browser holds the values, FormData reads them on submit.
export function SimpleForm({ fields, initial = {}, submitLabel, pending, error, onSubmit, onCancel }: Props) {
  const id = useId()
  return (
    <form
      className="grid gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        const form = e.currentTarget
        try {
          await onSubmit(Object.fromEntries(new FormData(form)) as Record<string, string>)
          form.reset()
        } catch {
          // shown through the `error` prop
        }
      }}
    >
      {fields.map((f) => {
        const props = { id: id + f.name, name: f.name, required: f.required, defaultValue: initial[f.name] ?? '' }
        return (
          <div key={f.name} className="grid gap-1.5">
            <Label htmlFor={props.id}>{f.label}</Label>
            {f.multiline ? (
              <Textarea {...props} />
            ) : f.type === 'password' ? (
              <PasswordInput {...props} autoComplete={f.autoComplete} minLength={f.minLength} />
            ) : (
              <Input {...props} type={f.type} autoComplete={f.autoComplete} minLength={f.minLength} />
            )}
            {f.hint && <p className="text-xs text-muted-foreground">{f.hint}</p>}
          </div>
        )
      })}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error.message}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" pending={pending}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}

/** A password box with an eye button that shows what was typed. Edge's own reveal icon is hidden so there's one eye. */
function PasswordInput(props: ComponentProps<'input'>) {
  const [shown, setShown] = useState(false)
  return (
    <div className="relative">
      <Input {...props} type={shown ? 'text' : 'password'} className="pr-9 [&::-ms-reveal]:hidden" />
      <Button type="button" variant="ghost" size="icon-sm" className="absolute top-0.5 right-0.5 text-muted-foreground"
              aria-label={shown ? 'Hide password' : 'Show password'} aria-controls={props.id} onClick={() => setShown(!shown)}>
        {shown ? <EyeOff /> : <Eye />}
      </Button>
    </div>
  )
}
