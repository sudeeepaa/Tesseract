import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppProviders } from './state/app';
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

/* ── Splash screen ──────────────────────────────────────────────────────────── */
const SPLASH_DURATION = 1500;  // ms before fade-out starts
const FADE_OUT = 400;          // ms for the fade-out transition

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

const SplashScreen: React.FC<{ onDone: () => void }> = ({ onDone }) => {
  const [fading, setFading] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setFading(true), SPLASH_DURATION);
    const t2 = setTimeout(onDone, SPLASH_DURATION + FADE_OUT);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [onDone]);

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
        <span style={splashStyles.sub}>Your AI Chief of Staff</span>
      </div>
    </div>
  );
};

/* ── App ────────────────────────────────────────────────────────────────────── */
export const App: React.FC = () => {
  const [showSplash, setShowSplash] = useState(true);

  return (
    <AppProviders>
      {showSplash && <SplashScreen onDone={() => setShowSplash(false)} />}
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
    </AppProviders>
  );
};

export default App;
