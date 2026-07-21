import React, {
  createContext, useCallback, useContext, useEffect, useRef, useState,
} from 'react';
import { CheckCircle2, AlertCircle } from 'lucide-react';
import { apiClient, BackendStatus, ConflictRecord } from '../api/client';

/* ── Theme ─────────────────────────────────────────────────────────────────── */
type Theme = 'light' | 'dark';
const THEME_KEY = 'tesseract-theme';

function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

interface ThemeCtx { theme: Theme; toggle: () => void; }
const ThemeContext = createContext<ThemeCtx>({ theme: 'light', toggle: () => {} });
export const useTheme = () => useContext(ThemeContext);

/* ── Toasts ────────────────────────────────────────────────────────────────── */
interface Toast { id: number; message: string; kind: 'success' | 'error'; }
interface ToastCtx { notify: (message: string, kind?: 'success' | 'error') => void; }
const ToastContext = createContext<ToastCtx>({ notify: () => {} });
export const useToast = () => useContext(ToastContext);

/* ── App data (status + conflicts, shared by sidebar bell and Home) ─────────── */
interface AppDataCtx {
  status: BackendStatus | null;
  online: boolean;
  conflicts: ConflictRecord[];
  unresolvedCount: number;
  refreshStatus: () => void;
  refreshConflicts: () => Promise<void>;
}
const AppDataContext = createContext<AppDataCtx>({
  status: null, online: true, conflicts: [], unresolvedCount: 0,
  refreshStatus: () => {}, refreshConflicts: async () => {},
});
export const useAppData = () => useContext(AppDataContext);

/* ── Combined provider ─────────────────────────────────────────────────────── */
export const AppProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Theme
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(THEME_KEY) as Theme) || systemTheme()
  );
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark';
      localStorage.setItem(THEME_KEY, next);
      return next;
    });
  }, []);

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);
  const notify = useCallback((message: string, kind: 'success' | 'error' = 'success') => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);

  // Data
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [online, setOnline] = useState(true);
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  const mounted = useRef(true);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await apiClient.getStatus();
      if (!mounted.current) return;
      setStatus(s); setOnline(true);
    } catch {
      if (mounted.current) setOnline(false);
    }
  }, []);

  const refreshConflicts = useCallback(async () => {
    try {
      const r = await apiClient.listConflicts();
      if (!mounted.current) return;
      setConflicts(r.conflicts); setOnline(true);
    } catch {
      if (mounted.current) setOnline(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    refreshStatus();
    refreshConflicts();
    const a = setInterval(refreshStatus, 20000);
    const b = setInterval(refreshConflicts, 15000);
    return () => { mounted.current = false; clearInterval(a); clearInterval(b); };
  }, [refreshStatus, refreshConflicts]);

  const unresolvedCount = conflicts.filter((c) => !c.resolved).length;

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      <ToastContext.Provider value={{ notify }}>
        <AppDataContext.Provider
          value={{ status, online, conflicts, unresolvedCount, refreshStatus, refreshConflicts }}
        >
          {children}
          <div className="toast-wrap" role="status" aria-live="polite">
            {toasts.map((t) => (
              <div key={t.id} className={`toast toast-${t.kind}`}>
                {t.kind === 'success'
                  ? <CheckCircle2 size={17} color="var(--green)" />
                  : <AlertCircle size={17} color="var(--red)" />}
                <span>{t.message}</span>
              </div>
            ))}
          </div>
        </AppDataContext.Provider>
      </ToastContext.Provider>
    </ThemeContext.Provider>
  );
};
