import type { ReactNode } from 'react';

export function Panel({ title, icon, actions, children, className = '', bodyClassName = 'p-4', id }: { title?: ReactNode; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClassName?: string; id?: string }) {
  return (
    <section id={id} className={`rounded-xl border border-white/[0.07] bg-ink-850/90 shadow-panel ${className}`}>
      {title && (
        <header className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-2.5">
          <h2 className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.08em] text-slate-300">
            {icon}
            {title}
          </h2>
          {actions}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function Skeleton({ className = 'h-24' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-white/[0.05] ${className}`} aria-hidden />;
}

export function ErrorNote({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-red-500/40 bg-red-950/40 p-3 text-sm text-red-200">
      {typeof error === 'string' ? error : error.message}
      {onRetry && (
        <button type="button" onClick={onRetry} className="ml-3 underline underline-offset-2 hover:text-white">
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center text-slate-400">
      {icon && <div className="text-slate-500">{icon}</div>}
      <p className="font-medium text-slate-200">{title}</p>
      {children && <div className="max-w-sm text-sm">{children}</div>}
    </div>
  );
}
