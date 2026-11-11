import { useEffect, useState } from 'react';
import { Pause, Play, RotateCcw, SkipForward, FlaskConical } from 'lucide-react';
import { useApi } from '../state/api-context';
import { fmtTime } from '../lib/format';

const SPEEDS = [0.5, 1, 2, 4] as const;
const BASE_MS = 2600;

export function DemoPill({ className = '' }: { className?: string }) {
  return (
    <span
      data-testid="demo-pill"
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-fuchsia-400/40 bg-fuchsia-500/15 px-2.5 py-0.5 text-[11px] font-semibold tracking-wide text-fuchsia-200 ${className}`}
    >
      <FlaskConical className="h-3.5 w-3.5" aria-hidden />
      DEMO · synthetic replay inspired by Assam monsoon floods
    </span>
  );
}

/** Replay controls for demo mode: play/pause, frame slider, speed, timestamp and caption. */
export function DemoBar({ compact = false }: { compact?: boolean }) {
  const { demo } = useApi();
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);

  useEffect(() => {
    if (!playing || !demo) return;
    const id = setInterval(() => {
      if (demo.frameIndex >= demo.frameCount - 1) {
        setPlaying(false);
        return;
      }
      demo.nextFrame();
    }, BASE_MS / speed);
    return () => clearInterval(id);
  }, [playing, speed, demo]);

  if (!demo) return null;
  const f = demo.frame;
  if (compact) {
    return (
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-fuchsia-200 bg-fuchsia-50 px-3 py-1.5 text-xs text-fuchsia-950" data-testid="demo-bar">
        <span data-testid="demo-pill" className="font-semibold">
          DEMO · synthetic replay inspired by Assam monsoon floods
        </span>
        <span className="font-mono">{fmtTime(f.t)} IST</span>
      </div>
    );
  }
  const atEnd = demo.frameIndex >= demo.frameCount - 1;

  return (
    <div className="border-b border-white/[0.06] bg-ink-950/80 backdrop-blur" data-testid="demo-bar">
      <div className="mx-auto flex max-w-[1920px] flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2 sm:px-5">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              if (atEnd) demo.setFrame(0);
              setPlaying((p) => !p);
            }}
            className="btn-icon bg-sky-500 text-white hover:bg-sky-400"
            aria-label={playing ? 'Pause replay' : 'Play replay'}
            data-testid="demo-play"
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </button>
          <button type="button" onClick={() => demo.nextFrame()} disabled={atEnd} className="btn-icon text-slate-300 hover:bg-white/10 disabled:opacity-40" aria-label="Next frame">
            <SkipForward className="h-4 w-4" />
          </button>
          <label className="sr-only" htmlFor="demo-speed">Replay speed</label>
          <select id="demo-speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value) as (typeof SPEEDS)[number])} className="h-8 rounded-md border border-white/10 bg-ink-800 px-1.5 text-xs text-slate-200">
            {SPEEDS.map((s) => (
              <option key={s} value={s}>
                {s}×
              </option>
            ))}
          </select>
        </div>
        <div className="flex min-w-[180px] flex-1 items-center gap-3">
          <label htmlFor="demo-frame" className="sr-only">Replay frame</label>
          <input
            id="demo-frame"
            data-testid="demo-frame"
            type="range"
            min={0}
            max={demo.frameCount - 1}
            value={demo.frameIndex}
            onChange={(e) => {
              setPlaying(false);
              demo.setFrame(Number(e.target.value));
            }}
            className="jr-range w-full max-w-[420px]"
            aria-valuetext={`Frame ${demo.frameIndex + 1} of ${demo.frameCount}, ${fmtTime(f.t)} IST`}
          />
          <span className="whitespace-nowrap font-mono text-xs tabular-nums text-slate-300">
            <span className="text-slate-500">T+{String(demo.frameIndex * 3).padStart(2, '0')}h</span> · {fmtTime(f.t)} IST
          </span>
        </div>
        <p className="min-w-0 flex-[2] basis-[320px] truncate text-xs text-slate-300" title={f.caption} data-testid="demo-caption">
          <span className="mr-2 font-semibold text-slate-500">
            {demo.frameIndex + 1}/{demo.frameCount}
          </span>
          {f.caption}
        </p>
        <div className="flex items-center gap-2">
          <DemoPill />
          <button
            type="button"
            onClick={() => {
              setPlaying(false);
              demo.reset();
            }}
            className="btn-icon text-slate-400 hover:bg-white/10 hover:text-white"
            aria-label="Reset demo (frame 1, clear approvals)"
            title="Reset demo (frame 1, clear approvals)"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
