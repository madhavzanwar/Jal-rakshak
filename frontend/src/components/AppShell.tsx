import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Bot, LayoutDashboard, ShieldCheck, Smartphone, WifiOff, Cpu } from 'lucide-react';
import { Logo, Wordmark } from './Logo';
import { DemoBar } from './DemoBar';
import { useApi } from '../state/api-context';

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/agents', label: 'Agents', icon: Bot, end: false },
  { to: '/admin', label: 'Admin', icon: ShieldCheck, end: false },
  { to: '/citizen', label: 'Citizen', icon: Smartphone, end: false },
];

export function Footer({ light = false }: { light?: boolean }) {
  return (
    <footer className={`border-t px-4 py-3 text-center text-[11px] leading-relaxed ${light ? 'border-slate-200 bg-white text-slate-600' : 'border-white/[0.06] bg-ink-950 text-slate-400'}`}>
      Decision support prototype · Data: Open-Meteo (GloFAS, ECMWF/ICON…),{' '}
      <a className="underline underline-offset-2" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
        © OpenStreetMap contributors
      </a>{' '}
      · <strong className={light ? 'text-slate-800' : 'text-slate-200'}>Not an official warning — follow IMD/NDMA/SDMA</strong>
    </footer>
  );
}

function ModeBadge() {
  const { client, health } = useApi();
  if (client.mode === 'demo') {
    return (
      <span className="hidden items-center gap-1.5 rounded-md border border-white/10 px-2 py-1 text-[11px] text-slate-400 xl:inline-flex" title="Agent outputs recorded with this model">
        <Cpu className="h-3.5 w-3.5" aria-hidden /> recorded with {health?.llm.provider}/{health?.llm.model}
      </span>
    );
  }
  return (
    <span className="hidden items-center gap-1.5 rounded-md border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-200 md:inline-flex">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" aria-hidden />
      LIVE · LLM {health?.llm.provider}/{health?.llm.model}
      {health && !health.llm.available && <span className="text-amber-300">(fallback: rules)</span>}
    </span>
  );
}

export function AppShell() {
  const { fallbackReason } = useApi();
  const loc = useLocation();
  const light = loc.pathname.startsWith('/citizen');
  return (
    <div className={`flex min-h-screen flex-col lg:h-screen ${light ? 'bg-slate-50 text-slate-900' : 'bg-ink-900 text-slate-100'}`}>
      <a href="#main" className="skip-link">Skip to content</a>
      <header className="sticky top-0 z-[1100] border-b border-white/[0.06] bg-ink-950/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1920px] items-center gap-3 px-3 sm:px-5">
          <NavLink to="/" className="flex shrink-0 items-center gap-2 rounded-md" aria-label="JalRakshak home">
            <Logo className="h-8 w-8" />
            <span className="flex flex-col leading-none">
              <Wordmark className="text-lg" />
              <span className="hidden text-[10px] uppercase tracking-[0.18em] text-slate-500 sm:block">Flood early warning · India</span>
            </span>
          </NavLink>
          <nav aria-label="Primary" className="ml-auto flex items-center gap-0.5 overflow-x-auto sm:ml-6">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1.5 text-sm font-medium transition-colors sm:px-3 ${
                    isActive ? 'bg-sky-500/15 text-sky-200' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
                  }`
                }
              >
                <Icon className="h-4 w-4" aria-hidden />
                <span className="hidden min-[420px]:inline">{label}</span>
                <span className="sr-only min-[420px]:hidden">{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto hidden items-center gap-2 sm:flex">
            <ModeBadge />
          </div>
        </div>
      </header>
      {fallbackReason && (
        <div role="status" data-testid="fallback-banner" className="flex items-center justify-center gap-2 border-b border-amber-400/30 bg-amber-500/15 px-4 py-1.5 text-center text-xs text-amber-100">
          <WifiOff className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {fallbackReason}
        </div>
      )}
      <DemoBar compact={light} />
      <main id="main" className="flex min-h-0 flex-1 flex-col lg:overflow-hidden" tabIndex={-1}>
        <Outlet />
      </main>
      <Footer light={light} />
    </div>
  );
}
