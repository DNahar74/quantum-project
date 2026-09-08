import React from 'react';

interface Column<T> {
  header: string;
  accessor: (row: T) => React.ReactNode;
}

interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (row: T) => string;
}

export function Table<T>({ data, columns, keyExtractor }: TableProps<T>) {
  if (data.length === 0) {
    return <div className="p-8 text-center text-slate-500">No data available</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((col, i) => (
              <th key={i} className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-200">
          {data.map((row) => (
            <tr key={keyExtractor(row)} className="hover:bg-slate-50 transition-colors">
              {columns.map((col, i) => (
                <td key={i} className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                  {col.accessor(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
