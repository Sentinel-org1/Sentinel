import React from 'react';
import Button from './Button';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionText?: string;
  onActionClick?: () => void;
  className?: string;
}

export default function EmptyState({
  icon,
  title,
  description,
  actionText,
  onActionClick,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center p-8 border border-dashed border-slate-800 rounded-xl bg-slate-900/20 backdrop-blur-sm ${className}`}>
      {icon ? (
        <div className="mb-4 text-slate-500">{icon}</div>
      ) : (
        <div className="mb-4 text-slate-600">
          <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
      )}
      <h3 className="text-base font-semibold text-slate-200 mb-1">{title}</h3>
      <p className="text-xs text-slate-450 max-w-xs mb-5 leading-relaxed">{description}</p>
      {actionText && onActionClick && (
        <Button variant="secondary" size="sm" onClick={onActionClick}>
          {actionText}
        </Button>
      )}
    </div>
  );
}
