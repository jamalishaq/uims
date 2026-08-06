import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import {
  useCredentials,
  useIssueCredential,
  useResetPassword,
  useSetCredentialActive,
} from '../../features/auth/queries'
import { ALL_ROLES, ROLE_LABEL } from '../../config/roles'
import useTitle from '../../hooks/useTitle'

/**
 * Who can sign in, at which level, and for which unit.
 *
 * **Issuing credentials cannot be delegated downwards**, which is why this page exists only
 * here: a faculty officer who could issue credentials could issue themselves a university-scoped
 * one, and every role gate in the system would become decorative.
 *
 * **A credential is never deleted, only disabled.** A login id freed for reissue is a login id
 * that once meant one principal and now means another — and an audit trail with one of those in
 * it has stopped being evidence.
 */
export default function Credentials() {
  useTitle('Credentials')
  const credentials = useCredentials()
  const issue = useIssueCredential()
  const setActive = useSetCredentialActive()

  const [filter, setFilter] = useState('')
  const { values, bind, reset } = useFields({
    login_id: '',
    principal_id: '',
    role: 'student',
    password: '',
    scope_unit_id: '',
  })

  const rows = (credentials.data ?? []).filter(
    (credential) =>
      !filter ||
      credential.login_id.toLowerCase().includes(filter.toLowerCase()) ||
      credential.principal_id.toLowerCase().includes(filter.toLowerCase()) ||
      credential.role === filter
  )

  return (
    <>
      <PageHeader
        title="Credentials"
        description="One login per unit. A student signs in with their matric number."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Every login"
            description={`${credentials.data?.length ?? 0} held`}
            action={
              <Input
                aria-label="Filter credentials"
                placeholder="Filter…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-40"
              />
            }
          />
          {credentials.isLoading ? (
            <Loading />
          ) : credentials.error ? (
            <CardBody>
              <ErrorNote error={credentials.error} />
            </CardBody>
          ) : rows.length === 0 ? (
            <EmptyState title="Nothing matches" description="No credential matches that filter." />
          ) : (
            <CardBody className="space-y-2">
              <ErrorNote error={setActive.error} title="Could not change that credential" />
              {rows.map((credential) => (
                <CredentialRow
                  key={credential.login_id}
                  credential={credential}
                  onToggle={() =>
                    setActive.mutate({
                      loginId: credential.login_id,
                      isActive: !credential.is_active,
                    })
                  }
                  busy={setActive.isPending}
                />
              ))}
            </CardBody>
          )}
        </Card>

        <div className="space-y-6">
          <FormCard
            title="Issue a credential"
            description="The login id is the id of the thing signing in."
            submitLabel="Issue credential"
            mutation={issue}
            onSubmit={() =>
              issue.mutate(
                {
                  loginId: values.login_id,
                  principalId: values.principal_id,
                  role: values.role,
                  password: values.password,
                  scopeUnitId: values.scope_unit_id || undefined,
                },
                { onSuccess: reset }
              )
            }
            successTitle="Credential issued"
            renderSuccess={(credential) => (
              <span>
                <span className="font-mono">{credential.login_id}</span> can now sign in as{' '}
                {ROLE_LABEL[credential.role]}.
              </span>
            )}
            footNote="A principal may hold only one credential. A second would be a second live password with no way to tell which is in use."
          >
            <Select label="Level" required {...bind('role')}>
              {ALL_ROLES.map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABEL[role]}
                </option>
              ))}
            </Select>
            <FieldRow>
              <Input
                label="Login id"
                required
                {...bind('login_id')}
                hint={
                  values.role === 'student'
                    ? 'Their matric number.'
                    : 'The id of the unit or person.'
                }
              />
              <Input
                label="Principal id"
                required
                {...bind('principal_id')}
                hint="The id the owning context minted."
              />
            </FieldRow>
            <Input
              label="Password"
              type="password"
              required
              {...bind('password')}
              hint="At least 8 characters. The server enforces the floor."
            />
            <Input
              label="Scope unit (optional)"
              {...bind('scope_unit_id')}
              hint="Defaults to the principal id. Only differs for a named office-holder."
            />
          </FormCard>

          <Note tone="warning" title="Disabling is not immediate">
            A disabled credential cannot sign in or refresh, but an access token already issued
            keeps working for up to thirty minutes. There is no server-side session store.
          </Note>
        </div>
      </div>
    </>
  )
}

function CredentialRow({ credential, onToggle, busy }) {
  const [resetting, setResetting] = useState(false)
  const [password, setPassword] = useState('')
  const resetPassword = useResetPassword()

  return (
    <div className="rounded-lg border border-ink-200 px-4 py-3 dark:border-ink-800">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm font-medium text-ink-900 dark:text-ink-100">
            {credential.login_id}
          </p>
          <p className="hint">
            {ROLE_LABEL[credential.role] ?? credential.role} ·{' '}
            <span className="font-mono">{credential.scope_id}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={credential.is_active ? 'success' : 'danger'}>
            {credential.is_active ? 'Active' : 'Disabled'}
          </Badge>
          <Button size="sm" variant="ghost" onClick={() => setResetting((r) => !r)}>
            Reset password
          </Button>
          <Button
            size="sm"
            variant={credential.is_active ? 'secondary' : 'primary'}
            loading={busy}
            onClick={onToggle}
          >
            {credential.is_active ? 'Disable' : 'Enable'}
          </Button>
        </div>
      </div>

      {resetting && (
        <form
          className="mt-3 flex items-end gap-2 border-t border-ink-200 pt-3 dark:border-ink-800"
          onSubmit={(event) => {
            event.preventDefault()
            resetPassword.mutate(
              { loginId: credential.login_id, newPassword: password },
              {
                onSuccess: () => {
                  setPassword('')
                  setResetting(false)
                },
              }
            )
          }}
        >
          <Input
            label="New password"
            type="password"
            className="flex-1"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hint="Set without their old one. They are not notified."
          />
          <Button type="submit" size="sm" loading={resetPassword.isPending}>
            Set
          </Button>
        </form>
      )}
      <ErrorNote error={resetPassword.error} className="mt-2" />
    </div>
  )
}
