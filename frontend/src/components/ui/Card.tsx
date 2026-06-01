import React from 'react';

interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  footer?: React.ReactNode;
  hoverEffect?: boolean;
}

export default function Card({
  children,
  title,
  subtitle,
  footer,
  hoverEffect = true,
  className = '',
  ...props
}: CardProps) {
  return (
    <div
      className={`bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-xl overflow-hidden shadow-xl transition-all duration-300 ${
        hoverEffect ? 'hover:shadow-2xl hover:border-slate-700 hover:-translate-y-0.5' : ''
      } ${className}`}
      {...props}
    >
      {(title || subtitle) && (
        <div className="px-6 py-5 border-b border-slate-850">
          {title && (
            <h3 className="text-lg font-semibold text-slate-100 tracking-tight">
              {title}
            </h3>
          )}
          {subtitle && (
            <p className="mt-1 text-xs text-slate-400 font-medium">
              {subtitle}
            </p>
          )}
        </div>
      )}
      <div className="p-6">{children}</div>
      {footer && (
        <div className="px-6 py-4 bg-slate-950/40 border-t border-slate-850/60 flex items-center justify-end">
          {footer}
        </div>
      )}
    </div>
  );
}
