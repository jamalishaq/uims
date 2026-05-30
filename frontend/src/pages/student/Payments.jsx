import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import { useMyFees, useInitPayment, useVerifyPayment } from '../../features/fees/queries'

const col = createColumnHelper()

function statusColor(status) {
  if (!status) return 'default'
  const s = status.toLowerCase()
  if (s === 'paid' || s === 'completed') return 'success'
  if (s === 'partial') return 'warning'
  if (s === 'pending' || s === 'unpaid') return 'danger'
  return 'default'
}

function fmt(amount) {
  if (amount == null) return '—'
  return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', maximumFractionDigits: 0 }).format(amount)
}

export default function Payments() {
  useTitle('Fee Payments')

  const { data: fees = [], isLoading } = useMyFees()
  const { mutate: initPayment, isPending: initializing } = useInitPayment()
  const { mutate: verifyPayment, isPending: verifying } = useVerifyPayment()

  // Track which fee row has a pending payment reference
  const [pendingRef, setPendingRef] = useState({}) // { [feeId]: reference }

  const handlePayNow = (fee) => {
    initPayment(
      { fee_id: fee.id },
      {
        onSuccess: (data) => {
          const url = data?.authorization_url ?? data?.data?.authorization_url
          const ref = data?.reference ?? data?.data?.reference
          if (url) {
            window.open(url, '_blank', 'noopener,noreferrer')
          }
          if (ref) {
            setPendingRef((prev) => ({ ...prev, [fee.id]: ref }))
          }
          toast('Payment page opened. Complete payment then click Verify.', { icon: 'ℹ️' })
        },
        onError: (err) => {
          const msg = err?.response?.data?.detail || err?.message || 'Failed to initialize payment.'
          toast.error(msg)
        },
      }
    )
  }

  const handleVerify = (fee) => {
    const ref = pendingRef[fee.id]
    if (!ref) {
      toast.error('No payment reference found. Please initiate payment first.')
      return
    }
    verifyPayment(ref, {
      onSuccess: () => {
        toast.success('Payment verified successfully.')
        setPendingRef((prev) => {
          const next = { ...prev }
          delete next[fee.id]
          return next
        })
      },
      onError: (err) => {
        const msg = err?.response?.data?.detail || err?.message || 'Verification failed.'
        toast.error(msg)
      },
    })
  }

  const columns = useMemo(
    () => [
      col.accessor((row) => row.fee_type ?? row.type ?? row.name ?? '—', {
        id: 'type',
        header: 'Fee Type',
      }),
      col.accessor((row) => fmt(row.amount_due ?? row.amount), {
        id: 'amount_due',
        header: 'Amount Due',
      }),
      col.accessor((row) => fmt(row.amount_paid ?? row.paid), {
        id: 'amount_paid',
        header: 'Paid',
      }),
      col.accessor((row) => fmt(row.balance ?? (row.amount_due - (row.amount_paid ?? 0))), {
        id: 'balance',
        header: 'Balance',
      }),
      col.display({
        id: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const status = row.original.status ?? 'Pending'
          return <Badge color={statusColor(status)}>{status}</Badge>
        },
      }),
      col.display({
        id: 'action',
        header: '',
        cell: ({ row }) => {
          const fee = row.original
          const status = (fee.status ?? '').toLowerCase()
          const isPending = ['pending', 'unpaid', 'partial'].includes(status)
          const hasRef = !!pendingRef[fee.id]

          if (!isPending) return null

          return (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="primary"
                loading={initializing}
                onClick={() => handlePayNow(fee)}
              >
                Pay Now
              </Button>
              {hasRef && (
                <Button
                  size="sm"
                  variant="secondary"
                  loading={verifying}
                  onClick={() => handleVerify(fee)}
                >
                  Verify Payment
                </Button>
              )}
            </div>
          )
        },
      }),
    ],
    [initializing, verifying, pendingRef] // eslint-disable-line react-hooks/exhaustive-deps
  )

  return (
    <div>
      <PageHeader
        title="Fee Payments"
        subtitle="View your fee schedule and make payments."
      />
      <Table
        columns={columns}
        data={fees}
        isLoading={isLoading}
        emptyMessage="No fee records found."
      />
    </div>
  )
}
