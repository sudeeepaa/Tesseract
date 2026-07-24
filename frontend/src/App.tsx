import React, { useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { AppProviders } from './state/app';
import { apiClient } from './api/client';
import { Shell } from './components/Shell';

import { HomeView } from './views/Home';
import { MeetingsView } from './views/Meetings';
import { DecisionsView } from './views/Decisions';
import { ActionItemsView } from './views/ActionItems';
import { AskView } from './views/Ask';
import { MapView } from './views/Map';
import { AddMeetingView } from './views/AddMeeting';
import { SettingsView } from './views/Settings';
import { LandingView } from './views/Landing';

/* ── Boot gate / splash ─────────────────────────────────────────────────────── */
const MIN_SPLASH = 900;   // keep the brand on screen at least this long (warm start)
const COLD_AFTER = 2500;  // if the backend hasn't answered by now, show the cold-start note
const SLOW_AFTER = 45000; // reassure the user if it's really taking a while
const FADE_OUT = 400;     // ms for the fade-out transition
const POLL_EVERY = 2000;  // gap between health pings while waking the backend

const splashStyles: Record<string, React.CSSProperties> = {
  wrapper: {
    position: 'fixed',
    inset: 0,
    zIndex: 100,
    display: 'grid',
    placeItems: 'center',
    background: 'var(--bg)',
    transition: `opacity ${FADE_OUT}ms ease, transform ${FADE_OUT}ms ease`,
  },
  inner: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 14,
    animation: 'splash-enter 600ms cubic-bezier(0.34, 1.56, 0.64, 1)',
  },
  mark: {
    width: 52,
    height: 52,
    borderRadius: 14,
    background: 'var(--text)',
    color: 'var(--bg)',
    display: 'grid',
    placeItems: 'center',
    fontWeight: 700,
    fontSize: 28,
    fontFamily: 'var(--font-sans)',
  },
  name: {
    fontWeight: 650,
    fontSize: 22,
    letterSpacing: '-0.01em',
    color: 'var(--text)',
    fontFamily: 'var(--font-sans)',
  },
  sub: {
    fontSize: 13,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-sans)',
    marginTop: -6,
  },
};

/** Branded splash that doubles as a cold-start gate: it pings the backend and
 *  stays on screen (with a "waking up" note) until the server responds, so a
 *  Render free-tier spin-up never dumps the user into a broken-looking app. */
const BootGate: React.FC<{ onReady: () => void }> = ({ onReady }) => {
  const [fading, setFading] = useState(false);
  const [cold, setCold] = useState(false);
  const [slow, setSlow] = useState(false);
  const startRef = useRef(Date.now());

  useEffect(() => {
    let active = true;
    const coldTimer = setTimeout(() => { if (active) setCold(true); }, COLD_AFTER);
    const slowTimer = setTimeout(() => { if (active) setSlow(true); }, SLOW_AFTER);

    async function poll() {
      while (active) {
        const ok = await apiClient.ping();
        if (!active) return;
        if (ok) {
          // Hold the brand for a graceful minimum, then fade into the app.
          const wait = Math.max(0, MIN_SPLASH - (Date.now() - startRef.current));
          setTimeout(() => {
            if (!active) return;
            setFading(true);
            setTimeout(() => { if (active) onReady(); }, FADE_OUT);
          }, wait);
          return;
        }
        await new Promise((r) => setTimeout(r, POLL_EVERY));
      }
    }
    poll();

    return () => { active = false; clearTimeout(coldTimer); clearTimeout(slowTimer); };
  }, [onReady]);

  return (
    <div
      style={{
        ...splashStyles.wrapper,
        opacity: fading ? 0 : 1,
        transform: fading ? 'scale(1.04)' : 'scale(1)',
      }}
    >
      <div style={splashStyles.inner}>
        <div style={splashStyles.mark}>T</div>
        <span style={splashStyles.name}>Tesseract</span>
        {!cold ? (
          <span style={splashStyles.sub}>Your AI Chief of Staff</span>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, marginTop: 2 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--text-2)', fontSize: 14, fontFamily: 'var(--font-sans)' }}>
              <Loader2 size={15} className="spin" /> Waking up your assistant…
            </span>
            <span style={{ ...splashStyles.sub, maxWidth: 340, textAlign: 'center', lineHeight: 1.55, marginTop: 0 }}>
              This demo runs on free hosting that goes to sleep when idle, so the first
              load can take up to a minute. Thanks for your patience — no need to refresh.
            </span>
            {slow && (
              <span style={{ fontSize: 12.5, color: 'var(--amber)', fontFamily: 'var(--font-sans)' }}>
                Still starting up… hang tight, almost there.
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/* ── App ────────────────────────────────────────────────────────────────────── */
export const App: React.FC = () => {
  const [ready, setReady] = useState(false);

  return (
    <AppProviders>
      {!ready ? (
        <BootGate onReady={() => setReady(true)} />
      ) : (
        <BrowserRouter>
          <Shell>
            <Routes>
              <Route path="/" element={<HomeView />} />
              <Route path="/landing" element={<LandingView />} />
              <Route path="/meetings" element={<MeetingsView />} />
              <Route path="/decisions" element={<DecisionsView />} />
              <Route path="/tasks" element={<ActionItemsView />} />
              <Route path="/ask" element={<AskView />} />
              <Route path="/map" element={<MapView />} />
              <Route path="/add" element={<AddMeetingView />} />
              <Route path="/settings" element={<SettingsView />} />
            </Routes>
          </Shell>
        </BrowserRouter>
      )}
    </AppProviders>
  );
};

export default App;
