import { useState } from 'react'
import Button from './ui/Button'
import Card, { CardBody, CardFooter, CardHeader } from './ui/Card'
import { ErrorNote, Note } from './ui/Feedback'

/**
 * A card with a form in it, its submit button, and its three outcomes.
 *
 * Almost every write in this app is the same shape — some fields, one mutation, and an error or
 * a confirmation — and the repetition is not just tedious: it is where inconsistency creeps in.
 * The pattern this enforces is that **the server's message is what gets shown**. Refusals here
 * are unusually informative ("quota exhausted", "no session-fee charge on record", "that
 * lecturer does not teach this course") and a page that replaced them with "Save failed" would
 * be throwing away the most useful thing the API sends.
 */
export function FormCard({
  title,
  description,
  submitLabel = 'Save',
  variant = 'primary',
  mutation,
  onSubmit,
  successTitle = 'Done',
  renderSuccess,
  children,
  footNote,
}) {
  const { isPending, error, data, reset } = mutation

  return (
    <Card>
      <CardHeader title={title} description={description} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit(event)
        }}
      >
        <CardBody className="space-y-4">
          {children}
          <ErrorNote error={error} />
          {data && (
            <Note tone="success" title={successTitle}>
              {renderSuccess ? renderSuccess(data) : null}
            </Note>
          )}
          {footNote && <p className="hint">{footNote}</p>}
        </CardBody>
        <CardFooter>
          {(error || data) && (
            <Button variant="ghost" size="sm" onClick={reset}>
              Clear
            </Button>
          )}
          <Button type="submit" variant={variant} loading={isPending}>
            {submitLabel}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}

/**
 * Controlled fields without a form library.
 *
 * `react-hook-form` and `zod` are still dependencies and still the right choice for the
 * application form, which has fifteen fields and cross-field rules. These panels have three or
 * four, and the validation that matters — is this quota positive, does this programme exist,
 * is this combination already published — is the server's and cannot be duplicated here
 * without becoming a second, quietly diverging copy of the domain.
 */
export function useFields(initial) {
  const [values, setValues] = useState(initial)

  const bind = (name, transform) => ({
    value: values[name],
    onChange: (event) => {
      const raw = event?.target ? event.target.value : event
      setValues((current) => ({ ...current, [name]: transform ? transform(raw) : raw }))
    },
  })

  return { values, setValues, bind, reset: () => setValues(initial) }
}

/** A row of fields that stacks on a phone. Two columns is the widest a form should ever be. */
export function FieldRow({ children, columns = 2 }) {
  return (
    <div className={`grid gap-4 ${columns === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
      {children}
    </div>
  )
}
