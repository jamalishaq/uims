import { useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table'
import Button from './Button'
import EmptyState from '../EmptyState'

export { createColumnHelper }

const SKELETON_ROWS = 5

export default function Table({
  columns,
  data = [],
  isLoading = false,
  emptyMessage = 'No results found',
  pagination,
  className = '',
}) {
  const [sorting, setSorting] = useState([])

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
  })

  const headerGroups = table.getHeaderGroups()
  const rows = table.getRowModel().rows

  // Pagination calculations
  let paginationBar = null
  if (pagination) {
    const { page, per_page, total, pages, onPageChange } = pagination
    const start = total === 0 ? 0 : (page - 1) * per_page + 1
    const end = Math.min(page * per_page, total)

    paginationBar = (
      <div className="flex items-center justify-between px-4 py-3 border-t border-ink-200 dark:border-ink-800 text-sm text-ink-600 dark:text-ink-400">
        <span>
          Showing {start}–{end} of {total}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            Prev
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`overflow-hidden rounded-xl border border-ink-200 bg-white dark:border-ink-800 dark:bg-ink-900 ${className}`}
    >
      {/* The table scrolls inside this box. A wide column set must never make the page itself
          scroll sideways — on a phone that moves the nav off screen. */}
      <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-ink-50 dark:bg-ink-800/60">
          {headerGroups.map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const canSort = header.column.getCanSort()
                const sortDir = header.column.getIsSorted()

                return (
                  <th
                    key={header.id}
                    className={`px-4 py-3 text-left text-xs font-medium text-ink-500 dark:text-ink-400 uppercase tracking-wide whitespace-nowrap${
                      canSort
                        ? ' cursor-pointer select-none hover:text-ink-700 dark:hover:text-ink-200'
                        : ''
                    }`}
                    onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                  >
                    <span className="inline-flex items-center gap-1">
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                      {sortDir === 'asc' && <span aria-hidden="true">↑</span>}
                      {sortDir === 'desc' && <span aria-hidden="true">↓</span>}
                    </span>
                  </th>
                )
              })}
            </tr>
          ))}
        </thead>

        <tbody>
          {isLoading
            ? Array.from({ length: SKELETON_ROWS }).map((_, rowIdx) => (
                <tr
                  key={rowIdx}
                  className="border-t border-ink-200 dark:border-ink-800"
                >
                  {headerGroups[0]?.headers.map((header) => (
                    <td key={header.id} className="px-4 py-3">
                      <div className="h-4 rounded bg-ink-200 dark:bg-ink-800 animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-t border-ink-200 dark:border-ink-800 hover:bg-ink-50 dark:hover:bg-ink-800/40 transition-colors duration-150"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-3 text-ink-700 dark:text-ink-300"
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>
      </div>

      {!isLoading && data.length === 0 && (
        <EmptyState title={emptyMessage} />
      )}

      {paginationBar}
    </div>
  )
}
