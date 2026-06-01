import React, { useEffect, useState } from 'react';
import client from '../api/client';
import { useStore, Alert } from '../store';
import useAlerts from '../hooks/useAlerts';
import Table from '../components/ui/Table';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';

export default function Alerts() {
  const models = useStore((state) => state.models);
  const updateAlertStatus = useStore((state) => state.updateAlertStatus);

  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Use alerts hook
  const { alerts, isLoading, refetch } = useAlerts(selectedModelId);

  // Filter alerts by status locally
  const filteredAlerts = alerts.filter((a) => {
    if (selectedStatus === 'all') return true;
    return a.status === selectedStatus;
  });

  // Paginate alerts
  const totalPages = Math.ceil(filteredAlerts.length / pageSize);
  const paginatedAlerts = filteredAlerts.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  const handleUpdateStatus = async (alertId: number, status: 'acknowledged' | 'resolved') => {
    try {
      await client.patch(`/api/alerts/${alertId}`, {
        status,
        comment: `Updated to ${status} via Alerts management console`,
      });
      updateAlertStatus(alertId, status);
    } catch (err) {
      console.error('Failed to update alert status:', err);
      alert('Failed to update alert status');
    }
  };

  const columns = [
    {
      header: 'ID',
      accessor: (row: Alert) => <span className="text-slate-500">#{row.id}</span>,
    },
    {
      header: 'Model ID',
      accessor: (row: Alert) => {
        const modelName = models.find((m) => m.id === row.model_id)?.name || `Model #${row.model_id}`;
        return <span className="font-semibold text-slate-200">{modelName}</span>;
      },
    },
    {
      header: 'Drift Event ID',
      accessor: (row: Alert) => <span className="text-slate-455">#{row.drift_event_id}</span>,
    },
    {
      header: 'Severity',
      accessor: (row: Alert) => {
        const variants = {
          critical: 'critical' as const,
          warn: 'warn' as const,
          info: 'info' as const,
        };
        return <Badge variant={variants[row.severity]}>{row.severity}</Badge>;
      },
    },
    {
      header: 'Status',
      accessor: (row: Alert) => {
        const variants = {
          open: 'critical' as const,
          acknowledged: 'warn' as const,
          resolved: 'success' as const,
        };
        return <Badge variant={variants[row.status]}>{row.status}</Badge>;
      },
    },
    {
      header: 'Created At',
      accessor: (row: Alert) =>
        new Date(row.created_at).toLocaleString([], {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }),
    },
    {
      header: 'Actions',
      accessor: (row: Alert) => (
        <div className="flex space-x-2">
          {row.status === 'open' && (
            <Button
              variant="secondary"
              size="sm"
              className="!py-1 !px-2.5 !text-[10px]"
              onClick={() => handleUpdateStatus(row.id, 'acknowledged')}
            >
              Acknowledge
            </Button>
          )}
          {row.status !== 'resolved' && (
            <Button
              variant="success"
              size="sm"
              className="!py-1 !px-2.5 !text-[10px]"
              onClick={() => handleUpdateStatus(row.id, 'resolved')}
            >
              Resolve
            </Button>
          )}
          {row.status === 'resolved' && <span className="text-[10px] text-slate-600 font-semibold italic">Resolved</span>}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0">
        <div>
          <h1 className="text-2xl font-black text-slate-100 tracking-tight">System Alerts Console</h1>
          <p className="text-xs text-slate-450 mt-1">Acknowledge, resolve, and audit ML operational warnings</p>
        </div>
        <Button variant="secondary" size="sm" onClick={refetch}>
          Refresh List
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-4 bg-slate-900/40 p-4 border border-slate-800 rounded-xl">
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Filter by Model</label>
          <select
            value={selectedModelId || ''}
            title="Filter by Model"
            onChange={(e) => {
              const val = e.target.value;
              setSelectedModelId(val ? parseInt(val, 10) : null);
              setCurrentPage(1);
            }}
            className="bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-lg px-3 py-1.5 text-xs text-slate-300 outline-none transition-all"
          >
            <option value="">All Models</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} (V{m.version})
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Filter by Status</label>
          <select
            value={selectedStatus}
            title="Filter by Status"
            onChange={(e) => {
              setSelectedStatus(e.target.value);
              setCurrentPage(1);
            }}
            className="bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-lg px-3 py-1.5 text-xs text-slate-300 outline-none transition-all"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
      </div>

      <Table
        columns={columns}
        data={paginatedAlerts}
        isLoading={isLoading}
        emptyMessage="No warnings found matching the active filters."
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={(page) => setCurrentPage(page)}
      />
    </div>
  );
}
