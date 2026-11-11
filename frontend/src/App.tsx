import { lazy, Suspense } from 'react';
import { HashRouter, Route, Routes } from 'react-router-dom';
import { ApiProvider } from './state/ApiProvider';
import { RunProvider } from './state/RunProvider';
import { AppShell } from './components/AppShell';

// Every page is its own chunk: the citizen route never downloads Leaflet, Recharts or jsPDF.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Agents = lazy(() => import('./pages/Agents'));
const Admin = lazy(() => import('./pages/Admin'));
const Citizen = lazy(() => import('./pages/Citizen'));

function PageFallback() {
  return (
    <div className="grid flex-1 place-items-center p-10 text-sm text-slate-400" role="status">
      Loading…
    </div>
  );
}

function NotFound() {
  return <div className="p-10 text-center text-slate-300">Page not found.</div>;
}

export default function App() {
  return (
    <ApiProvider>
      <RunProvider>
        <HashRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<Suspense fallback={<PageFallback />}><Dashboard /></Suspense>} />
              <Route path="agents" element={<Suspense fallback={<PageFallback />}><Agents /></Suspense>} />
              <Route path="admin" element={<Suspense fallback={<PageFallback />}><Admin /></Suspense>} />
              <Route path="citizen" element={<Suspense fallback={<PageFallback />}><Citizen /></Suspense>} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </HashRouter>
      </RunProvider>
    </ApiProvider>
  );
}
