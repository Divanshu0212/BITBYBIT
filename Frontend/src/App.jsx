import React, { useReducer, useEffect } from 'react';
import { reducer, initialState } from './store/reducer';
import { ACTIONS } from './store/actions';
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { clearAuth, getToken } from './api';
import { LineChart, Trophy, Search, Mail, Briefcase, BarChart2, LogOut, Zap, Building, User } from 'lucide-react';
import { ModeToggle } from './components/ModeToggle';

import AuthPage from './components/AuthPage';
import EscrowLedger from './components/EscrowLedger';
import EmployerDashboard from './components/EmployerDashboard';
import FreelancerDashboard from './components/FreelancerDashboard';
import PFIDashboard from './components/PFIDashboard';
import AnalyticsPanel from './components/AnalyticsPanel';
import HITLOverride from './components/HITLOverride';
import { Button } from './components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from './components/ui/card';
import { Badge } from './components/ui/badge';

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);

  const isLoggedIn = !!state.token && !!state.user;
  const isEmployer = state.user?.role === 'employer';
  const isFreelancer = state.user?.role === 'freelancer';

  const navigate = useNavigate();
  const location = useLocation();

  // Set default view based on role
  useEffect(() => {
    if (isLoggedIn && location.pathname === '/') {
      navigate(isFreelancer ? '/browse' : '/projects', { replace: true });
      dispatch({ type: ACTIONS.SET_VIEW, payload: isFreelancer ? 'browse' : 'projects' });
    }
  }, [isLoggedIn, location.pathname, isFreelancer, navigate]);

  const handleLogout = () => {
    clearAuth();
    dispatch({ type: ACTIONS.LOGOUT });
  };

  if (!isLoggedIn) {
    return <AuthPage dispatch={dispatch} />;
  }

  const NAV_ITEMS = isEmployer
    ? [
      { key: 'projects', icon: <Building size={18} />, label: 'My Projects' },
      { key: 'analytics', icon: <LineChart size={18} />, label: 'Analytics' },
      { key: 'leaderboard', icon: <Trophy size={18} />, label: 'PFI Leaderboard' },
    ]
    : [
      { key: 'browse', icon: <Search size={18} />, label: 'Find Work' },
      { key: 'proposals', icon: <Mail size={18} />, label: 'My Proposals' },
      { key: 'projects', icon: <Briefcase size={18} />, label: 'Active Projects' },
      { key: 'pfi', icon: <BarChart2 size={18} />, label: 'My PFI Score' },
      { key: 'leaderboard', icon: <Trophy size={18} />, label: 'Leaderboard' },
    ];

  // Routing is now handled by react-router-dom in the JSX directly

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon"><Zap size={22} color="var(--cyan)" /></span>
            <span className="logo-text">Snack Overflow</span>
          </div>
          <span className="logo-tagline">Autonomous AI Project & Payment Intermediary</span>
        </div>
        <div className="header-right">
          <ModeToggle />
          <div className="user-info">
            <span className="user-role-badge">
              {isEmployer ? <Building size={14} className="inline-block mr-1" /> : <User size={14} className="inline-block mr-1" />}
              {state.user.role}
            </span>
            <span className="user-name">{state.user.name}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout} title="Sign out" className="flex items-center gap-1.5 ml-2">
            <LogOut size={16} /> Logout
          </Button>
        </div>
      </header>

      {/* Main Layout */}
      <div className="app-layout">
        {/* Left Sidebar Navigation */}
        <nav className="sidebar">
          <div className="nav-links">
            {NAV_ITEMS.map(item => (
              <button
                key={item.key}
                className={`nav-btn ${location.pathname.includes(item.key) ? 'active' : ''}`}
                onClick={() => {
                  navigate(`/${item.key}`);
                  dispatch({ type: ACTIONS.SET_VIEW, payload: item.key });
                }}
              >
                <span className="nav-icon" style={{ display: 'flex' }}>{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </button>
            ))}
          </div>
          <div className="sidebar-footer">
            <div className="sidebar-user-mini">
              <div className="mini-email">{state.user.email}</div>
            </div>
          </div>
        </nav>

        {/* Center Content */}
        <main className="main-content">
          {/* HITL Override banner at top (employer only) */}
          {isEmployer && <HITLOverride state={state} dispatch={dispatch} />}
          {/* Main Route Content */}
          <Routes>
            <Route path="/projects" element={isEmployer ? <EmployerDashboard state={state} dispatch={dispatch} /> : <FreelancerDashboard state={state} dispatch={dispatch} mode="projects" />} />
            <Route path="/browse" element={<FreelancerDashboard state={state} dispatch={dispatch} mode="browse" />} />
            <Route path="/proposals" element={<FreelancerDashboard state={state} dispatch={dispatch} mode="proposals" />} />
            <Route path="/analytics" element={isEmployer ? <AnalyticsPanel state={state} dispatch={dispatch} /> : <Navigate to="/projects" replace />} />
            <Route path="/pfi" element={<PFIDashboard state={state} dispatch={dispatch} mode="self" />} />
            <Route path="/leaderboard" element={<PFIDashboard state={state} dispatch={dispatch} mode="leaderboard" />} />
            <Route path="*" element={<Navigate to={isEmployer ? '/projects' : '/browse'} replace />} />
          </Routes>
        </main>

        {/* Right Panel: Escrow Ledger */}
        <aside className="ledger-aside">
          <EscrowLedger state={state} dispatch={dispatch} />
        </aside>
      </div>
    </div>
  );
}
