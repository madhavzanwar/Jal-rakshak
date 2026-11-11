import { useId } from 'react';

/** Water drop inside a shield — the JalRakshak mark (same artwork as public/favicon.svg). */
export function Logo({ className = 'h-8 w-8', title = 'JalRakshak' }: { className?: string; title?: string }) {
  const id = useId().replace(/:/g, '');
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label={title}>
      <defs>
        <linearGradient id={`s${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#38bdf8" />
          <stop offset="1" stopColor="#0369a1" />
        </linearGradient>
        <linearGradient id={`d${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#e0f2fe" />
        </linearGradient>
      </defs>
      <path d="M32 3.5 55 11.5v18.8c0 14.6-9.6 25.6-23 30.7C18.6 55.9 9 44.9 9 30.3V11.5z" fill={`url(#s${id})`} />
      <path d="M32 14.5s-11 12.7-11 21.2a11 11 0 0 0 22 0c0-8.5-11-21.2-11-21.2z" fill={`url(#d${id})`} />
      <path d="M23.3 38.2c2.9-2.2 5.8-2.2 8.7 0s5.8 2.2 8.7 0" fill="none" stroke="#0284c7" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M25.6 43.2c2.1-1.5 4.2-1.5 6.4 0s4.3 1.5 6.4 0" fill="none" stroke="#0284c7" strokeOpacity=".6" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-tight ${className}`}>
      <span className="text-sky-300">Jal</span>
      <span className="text-white">Rakshak</span>
    </span>
  );
}
