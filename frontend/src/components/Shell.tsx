import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Home, ClipboardCheck, ListTodo, MessageCircleQuestion, Share2,
  Settings, Plus, Bell, Sun, Moon, Menu, CalendarDays, Compass,
} from 'lucide-react';
import { useAppData, useTheme } from '../state/app';
import { SystemStatus } from './SystemStatus';

const NAV = [
  { to: '/landing',   label: 'Overview & Purpose', icon: Compass },
  { to: '/',          label: 'Command Center', icon: Home,                  end: true },
  { to: '/meetings',  label: 'Meetings',       icon: CalendarDays },
  { to: '/decisions', label: 'Decisions',      icon: ClipboardCheck },
  { to: '/tasks',     label: 'Action items',   icon: ListTodo },
  { to: '/ask',       label: 'Ask',            icon: MessageCircleQuestion },
  { to: '/map',       label: 'Relationships',  icon: Share2 },
];

const TITLES: Record<string, string> = {
  '/landing': 'Overview & Platform Purpose',
  '/': 'Command Center', '/meetings': 'Meetings', '/decisions': 'Decisions',
  '/tasks': 'Action items', '/ask': 'Ask your meetings', '/map': 'Relationships',
  '/add': 'Add a meeting', '/settings': 'Settings',
};

const Sidebar: React.FC<{ open: boolean }> = ({ open }) => {
  const { unresolvedCount } = useAppData();
  return (
    <aside className={`sidebar${open ? ' open' : ''}`}>
      <div className="sidebar-brand">
        <div className="brand-mark">T</div>
        <div className="col">
          <span className="brand-name">Tesseract</span>
          <span className="brand-sub">Your AI Chief of Staff</span>
        </div>
      </div>

      <NavLink to="/add" className="btn btn-primary btn-block" style={{ marginBottom: 6 }}>
        <Plus size={16} /> Add a meeting
      </NavLink>

      <nav className="nav">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <Icon size={16} />
            <span>{label}</span>
            {to === '/' && unresolvedCount > 0 && <span className="nav-count">{unresolvedCount}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <NavLink to="/settings" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <Settings size={16} /><span>Settings &amp; privacy</span>
        </NavLink>
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
          <SystemStatus />
        </div>
      </div>
    </aside>
  );
};

const AlertBell: React.FC = () => {
  const { unresolvedCount } = useAppData();
  const navigate = useNavigate();
  return (
    <button className="icon-btn" onClick={() => navigate('/')} title={
      unresolvedCount > 0 ? `${unresolvedCount} decision(s) need you` : 'Nothing needs your attention'
    } style={{ position: 'relative' }}>
      <Bell size={17} />
      {unresolvedCount > 0 && (
        <span style={{
          position: 'absolute', top: 3, right: 3, minWidth: 15, height: 15, padding: '0 4px',
          borderRadius: 8, background: 'var(--red)', color: '#fff', fontSize: 10, fontWeight: 700,
          display: 'grid', placeItems: 'center', border: '2px solid var(--bg)',
        }}>{unresolvedCount}</span>
      )}
    </button>
  );
};

const TopBar: React.FC<{ onMenu: () => void }> = ({ onMenu }) => {
  const { pathname } = useLocation();
  const { theme, toggle } = useTheme();
  const title = TITLES[pathname] || 'Tesseract';
  return (
    <header className="topbar">
      <div className="row" style={{ gap: 8 }}>
        <button className="icon-btn menu-btn" onClick={onMenu} aria-label="Menu"><Menu size={18} /></button>
        <span className="topbar-title">{title}</span>
      </div>
      <div className="topbar-actions">
        <AlertBell />
        <button className="icon-btn" onClick={toggle} title="Toggle light / dark">
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>
      </div>
    </header>
  );
};

export const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => { setMenuOpen(false); }, [loc.pathname]);
  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} />
      <div className="main">
        <TopBar onMenu={() => setMenuOpen((o) => !o)} />
        {children}
      </div>
      {menuOpen && (
        <div className="overlay" style={{ zIndex: 30, background: 'rgba(15,15,15,0.3)' }}
          onClick={() => setMenuOpen(false)} />
      )}
    </div>
  );
};
