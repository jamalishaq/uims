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
      <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-400">
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
      className={`rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden ${className}`}
    >
      <table className="w-full text-sm border-collapse">
        <thead className="bg-slate-50 dark:bg-slate-800/60">
          {headerGroups.map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const canSort = header.column.getCanSort()
                const sortDir = header.column.getIsSorted()

                return (
                  <th
                    key={header.id}
                    className={`px-4 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide whitespace-nowrap${
                      canSort
                        ? ' cursor-pointer select-none hover:text-slate-700 dark:hover:text-slate-200'
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
                  className="border-t border-slate-200 dark:border-slate-700"
                >
                  {headerGroups[0]?.headers.map((header) => (
                    <td key={header.id} className="px-4 py-3">
                      <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-t border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors duration-150"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-3 text-slate-700 dark:text-slate-300"
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>

      {!isLoading && data.length === 0 && (
        <EmptyState title={emptyMessage} />
      )}

      {paginationBar}
    </div>
  )
}
