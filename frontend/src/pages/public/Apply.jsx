import { useState } from 'react'
import { Link } from 'react-router-dom'
import { GraduationCap } from 'lucide-react'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorNote, Note } from '../../components/ui/Feedback'
import { useSubmitApplication } from '../../features/admissions/queries'
import useTitle from '../../hooks/useTitle'

/**
 * The one page in this app that works without an account.
 *
 * `POST /admissions/applications` is public on the server for the reason it has to be:
 * somebody who has never had a credential applies through it, and requiring one would be a
 * deadlock. Everything else is behind a token.
 *
 * **Exactly four subjects, each 0–100.** That is the confirmed shape of a UTME result — the
 * count and the bounds are single constants in the domain — so the form renders four fixed rows
 * rather than an "add subject" list that could produce three or five and be refused.
 */
const SUBJECT_ROWS = 4

const emptyScores = Array.from({ length: SUBJECT_ROWS }, () => ({ subject: '', score: '' }))

export default function Apply() {
  useTitle('Apply for admission')
  const { mutate: apply, isPending, error, data } = useSubmitApplication()

  const [form, setForm] = useState({
    applicant_id: '',
    program_id: '',
    session_id: '',
    full_name: '',
    email: '',
    phone_number: '',
    date_of_birth: '',
  })
  const [scores, setScores] = useState(emptyScores)

  const setField = (name) => (event) => setForm((f) => ({ ...f, [name]: event.target.value }))

  const setScore = (index, key) => (event) =>
    setScores((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [key]: event.target.value } : row))
    )

  const submit = (event) => {
    event.preventDefault()
    apply({
      ...form,
      // The API forbids unknown fields and rejects empty strings where it wants null, so the
      // optionals are dropped rather than sent blank.
      email: form.email || null,
      phone_number: form.phone_number || null,
      date_of_birth: form.date_of_birth || null,
      utme_scores: scores.map(({ subject, score }) => ({
        subject: subject.trim(),
        score: Number(score),
      })),
    })
  }

  if (data) {
    return (
      <Shell>
        <Card>
          <CardHeader title="Application received" />
          <CardBody className="space-y-4">
            <Note tone="success" title={`Reference ${data.applicant_id}`}>
              Keep this reference. It is how the registry finds your application, and how you
              will be identified until a matric number is issued.
            </Note>
            <p className="text-sm text-ink-600 dark:text-ink-400">
              Your application is now <strong>{data.status}</strong>. Screening and the offer
              decision are automatic; the department registry runs them and will record the
              outcome against this reference.
            </p>
            <Link
              to="/login"
              className="inline-block text-sm font-medium text-brand-600 dark:text-brand-400"
            >
              Back to sign in
            </Link>
          </CardBody>
        </Card>
      </Shell>
    )
  }

  return (
    <Shell>
      <Card>
        <CardHeader
          title="Apply for admission"
          description="No account needed. You will be given a reference when this is submitted."
        />
        <CardBody>
          <form onSubmit={submit} className="space-y-6">
            <fieldset className="space-y-4">
              <legend className="mb-2 text-sm font-semibold text-ink-900 dark:text-ink-100">
                About you
              </legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="Full name"
                  required
                  value={form.full_name}
                  onChange={setField('full_name')}
                />
                <Input
                  label="Your reference"
                  required
                  value={form.applicant_id}
                  onChange={setField('applicant_id')}
                  hint="Your JAMB registration number."
                />
                <Input
                  label="Email"
                  type="email"
                  value={form.email}
                  onChange={setField('email')}
                />
                <Input
                  label="Phone number"
                  value={form.phone_number}
                  onChange={setField('phone_number')}
                  hint="Any format. No pattern is imposed."
                />
                <Input
                  label="Date of birth"
                  type="date"
                  value={form.date_of_birth}
                  onChange={setField('date_of_birth')}
                />
              </div>
            </fieldset>

            <fieldset className="space-y-4">
              <legend className="mb-2 text-sm font-semibold text-ink-900 dark:text-ink-100">
                Where you are applying
              </legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="Programme"
                  required
                  value={form.program_id}
                  onChange={setField('program_id')}
                  hint="The programme code, e.g. prog-csc."
                />
                <Input
                  label="Session"
                  required
                  value={form.session_id}
                  onChange={setField('session_id')}
                  hint="Required: a programme admits for a session, not in general."
                />
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-1 text-sm font-semibold text-ink-900 dark:text-ink-100">
                UTME result
              </legend>
              <p className="mb-3 hint">
                Exactly four subjects, each scored 0–100. Whether the combination qualifies you
                is decided at screening against the programme&rsquo;s published requirement.
              </p>
              <div className="space-y-3">
                {scores.map((row, index) => (
                  <div key={index} className="grid grid-cols-[1fr_7rem] gap-3">
                    <Input
                      aria-label={`Subject ${index + 1}`}
                      placeholder={index === 0 ? 'USE OF ENGLISH' : 'Subject'}
                      required
                      value={row.subject}
                      onChange={setScore(index, 'subject')}
                    />
                    <Input
                      aria-label={`Score for subject ${index + 1}`}
                      type="number"
                      min={0}
                      max={100}
                      required
                      value={row.score}
                      onChange={setScore(index, 'score')}
                    />
                  </div>
                ))}
              </div>
            </fieldset>

            <ErrorNote error={error} title="Your application was not accepted" />

            <div className="flex items-center justify-between gap-4">
              <Link to="/login" className="text-sm text-ink-500 hover:text-ink-700">
                Back to sign in
              </Link>
              <Button type="submit" size="lg" loading={isPending}>
                Submit application
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </Shell>
  )
}

function Shell({ children }) {
  return (
    <div className="min-h-dvh bg-ink-100 px-4 py-10 dark:bg-ink-950">
      <div className="mx-auto w-full max-w-2xl">
        <div className="mb-6 flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-600">
            <GraduationCap size={18} className="text-white" aria-hidden="true" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-ink-900 dark:text-ink-50">
            University MS
          </span>
        </div>
        {children}
      </div>
    </div>
  )
}
