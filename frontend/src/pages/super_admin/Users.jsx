import { useState } from 'react'
import toast from 'react-hot-toast'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import { useUsers, useToggleUserActive } from '../../features/users/queries'

const ROLES = ['All', 'student', 'lecturer', 'registrar', 'bursar', 'hod', 'dean', 'super_admin', 'applicant', 'alumni']
const STATUS_TABS = ['All', 'Active', 'Inactive']

const col = createColumnHelper()

export default function UsersPage() {
  useTitle('Users')

  const [roleFilter, setRoleFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')

  const queryParams = {}
  if (roleFilter !== 'All') queryParams.role = roleFilter.toUpperCase()
  if (statusFilter === 'Active') queryParams.is_active = true
  if (statusFilter === 'Inactive') queryParams.is_active = false

  const { data: users = [], isLoading } = useUsers(queryParams)
  const { mutate: toggleActive, isPending } = useToggleUserActive()

  function handleToggle(user) {
    if (user.is_active) {
      const confirmed = window.confirm(
        `Deactivate "${user.username}"? They will lose access immediately.`
      )
      if (!confirmed) return
    }

    toggleActive(user.id, {
      onSuccess: () =>
        toast.success(user.is_active ? 'User deactivated.' : 'User activated.'),
      onError: (err) =>
        toast.error(err?.response?.data?.message ?? err?.message ?? 'Something went wrong.'),
    })
  }

  const columns = [
    col.accessor('username', { header: 'Username' }),
    col.accessor('email', { header: 'Email' }),
    col.accessor('role', {
      header: 'Role',
      cell: (info) => {
        const role = info.getValue()
        return <Badge color="indigo">{role}</Badge>
      },
    }),
    col.accessor('is_active', {
      header: 'Status',
      cell: (info) =>
        info.getValue() ? (
          <Badge color="success">Active</Badge>
        ) : (
          <Badge color="danger">Inactive</Badge>
        ),
    }),
    col.display({
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const user = row.original
        return (
          <Button
            variant={user.is_active ? 'danger' : 'primary'}
            size="sm"
            disabled={isPending}
            onClick={() => handleToggle(user)}
          >
            {user.is_active ? 'Deactivate' : 'Activate'}
          </Button>
        )
      },
    }),
  ]

  return (
    <div className="space-y-6">
      <PageHeader title="Users" subtitle="Manage all system accounts" />

      {/* Role filter tabs */}
      <div className="flex flex-wrap gap-2">
        {ROLES.map((role) => (
          <button
            key={role}
            onClick={() => setRoleFilter(role)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors duration-150 ${
              roleFilter === role
                ? 'bg-indigo-600 text-white'
                : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
            }`}
          >
            {role === 'All' ? 'All' : role}
          </button>
        ))}
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-2">
        {STATUS_TABS.map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors duration-150 ${
              statusFilter === status
                ? 'bg-slate-700 dark:bg-slate-200 text-white dark:text-slate-900'
                : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {/* Users table */}
      <Card>
        <CardBody className="p-0">
          <Table
            columns={columns}
            data={users}
            isLoading={isLoading}
            emptyMessage="No users match the selected filters"
          />
        </CardBody>
      </Card>
    </div>
  )
}
