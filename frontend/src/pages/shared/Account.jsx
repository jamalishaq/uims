import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import PageHeader, { Detail } from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { useChangeMyPassword, useMe } from '../../features/auth/queries'
import { ROLE_LABEL } from '../../config/roles'
import useTitle from '../../hooks/useTitle'

/**
 * Your own credential, for all five roles.
 *
 * The identity read is `GET /auth/me`, which goes back to the server rather than reading the
 * stored principal. The route exists precisely so a credential deactivated or deleted since
 * this token was issued shows as such — an access token stays valid for up to thirty minutes
 * either way.
 *
 * **There is no name or email on this page**, and that is not a gap. Identity holds credentials,
 * role and scope only; a name lives in whichever context minted the principal, and putting one
 * here would make this the second place the university records who somebody is.
 */
export default function Account() {
  useTitle('My account')
  const { data: me, isLoading, error } = useMe()
  const changePassword = useChangeMyPassword()

  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [mismatch, setMismatch] = useState(false)

  const submit = (event) => {
    event.preventDefault()
    if (next !== confirm) {
      setMismatch(true)
      return
    }
    setMismatch(false)
    changePassword.mutate(
      { currentPassword: current, newPassword: next },
      {
        onSuccess: () => {
          setCurrent('')
          setNext('')
          setConfirm('')
        },
      }
    )
  }

  return (
    <>
      <PageHeader
        title="My account"
        description="The credential you signed in with, and the only thing on this page you can change."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Who you are signed in as" />
          {isLoading ? (
            <Loading />
          ) : error ? (
            <CardBody>
              <ErrorNote error={error} title="Could not read your credential" />
            </CardBody>
          ) : (
            <CardBody>
              <dl>
                <Detail label="Login id" value={me.login_id} mono />
                <Detail label="Role" value={ROLE_LABEL[me.role] ?? me.role} />
                <Detail label="Principal" value={me.principal_id} mono />
                <Detail label="Scope" value={`${me.scope_kind} · ${me.scope_id}`} mono />
                <Detail
                  label="Status"
                  value={
                    <Badge tone={me.is_active ? 'success' : 'danger'}>
                      {me.is_active ? 'Active' : 'Disabled'}
                    </Badge>
                  }
                />
              </dl>
              <p className="mt-4 hint">
                Your scope is the unit you may act on. Every page here is filtered to it, and the
                server checks it again on every request.
              </p>
            </CardBody>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Change your password"
            description="Only your own. Resetting somebody else's is the university's to do."
          />
          <form onSubmit={submit}>
            <CardBody className="space-y-4">
              <Input
                label="Current password"
                type="password"
                autoComplete="current-password"
                required
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
              <Input
                label="New password"
                type="password"
                autoComplete="new-password"
                required
                value={next}
                onChange={(e) => setNext(e.target.value)}
                hint="At least 8 characters. The server enforces the floor."
              />
              <Input
                label="Confirm new password"
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                error={mismatch ? 'These two do not match.' : undefined}
              />
              <ErrorNote error={changePassword.error} title="Password not changed" />
              {changePassword.data && (
                <Note tone="success" title="Password changed">
                  Sessions already open elsewhere are not ended — see the note below.
                </Note>
              )}
              <p className="hint">
                Changing your password does not sign out other browsers. There is no
                server-side session store, so an access token already issued stays valid for up
                to thirty minutes.
              </p>
              <Button type="submit" loading={changePassword.isPending}>
                Change password
              </Button>
            </CardBody>
          </form>
        </Card>
      </div>
    </>
  )
}
