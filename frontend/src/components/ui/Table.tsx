import React from 'react';
import Spinner from './Spinner';

export interface Column<T> {
  header: React.ReactNode;
  accessor: keyof T | ((row: T) => React.ReactNode);
  className?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
}

export default function Table<T>({
  columns,
  data,
  isLoading = false,
  onRowClick,
  emptyMessage = 'No data available',
  currentPage,
  totalPages,
  onPageChange,
}: TableProps<T>) {
  return (
    <div className="w-full flex flex-col">
      <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/40 backdrop-blur-xl">
        <table className="min-w-full divide-y divide-slate-800">
          <thead className="bg-slate-950/60">
            <tr>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  scope="col"
                  className={`px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider ${col.className || ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-850/60 bg-transparent">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center">
                  <div className="flex flex-col items-center justify-center space-y-3">
                    <Spinner size="lg" />
                    <span className="text-sm text-slate-400">Loading records...</span>
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center text-sm text-slate-500">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row, rowIdx) => (
                <tr
                  key={rowIdx}
                  onClick={() => onRowClick && onRowClick(row)}
                  className={`transition-colors duration-150 ${
                    onRowClick ? 'cursor-pointer hover:bg-slate-800/30' : 'hover:bg-slate-850/10'
                  }`}
                >
                  {columns.map((col, colIdx) => {
                    const value = typeof col.accessor === 'function'
                      ? col.accessor(row)
                      : (row[col.accessor] as React.ReactNode);
                    return (
                      <td
                        key={colIdx}
                        className={`px-6 py-4 text-sm text-slate-300 font-medium whitespace-nowrap ${col.className || ''}`}
                      >
                        {value}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {onPageChange && currentPage !== undefined && totalPages !== undefined && totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 px-4">
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="px-3 py-1.5 text-xs font-medium text-slate-400 bg-slate-800 rounded-md border border-slate-700 hover:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            Previous
          </button>
          <span className="text-xs text-slate-455">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 text-xs font-medium text-slate-400 bg-slate-800 rounded-md border border-slate-700 hover:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
