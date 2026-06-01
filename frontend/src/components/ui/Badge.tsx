import React from 'react';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'info' | 'warn' | 'critical' | 'success' | 'default';
  size?: 'sm' | 'md';
}

export default function Badge({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  ...props
}: BadgeProps) {
  const baseStyle = 'inline-flex items-center font-semibold rounded-full border tracking-wide uppercase';

  const variants = {
    default: 'bg-slate-800/40 text-slate-300 border-slate-700/60',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/25',
    warn: 'bg-amber-500/10 text-amber-400 border-amber-500/25',
    critical: 'bg-rose-500/10 text-rose-400 border-rose-500/25 animate-pulse',
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-[10px]',
    md: 'px-2.5 py-1 text-xs',
  };

  return (
    <span
      className={`${baseStyle} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
