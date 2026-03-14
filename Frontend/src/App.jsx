import React, { useReducer, useEffect } from 'react';
import { reducer, initialState } from './store/reducer';
import { ACTIONS } from './store/actions';
import { clearAuth, getToken } from './api';
import { LineChart, Trophy, Search, Mail, Briefcase, BarChart2, LogOut, Zap, Building, User } from 'lucide-react';

import AuthPage from './components/AuthPage';
import EscrowLedger from './components/EscrowLedger';
import EmployerDashboard from './components/EmployerDashboard';
import FreelancerDashboard from './components/FreelancerDashboard';
import PFIDashboard from './components/PFIDashboard';
import AnalyticsPanel from './components/AnalyticsPanel';
import HITLOverride from './components/HITLOverride';

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);

  const isLoggedIn = !!state.token && !!state.user;
  const isEmployer = state.user?.role === 'employer';
  const isFreelancer = state.user?.role === 'freelancer';

  // Set default view based on role
  useEffect(() => {
    if (isLoggedIn) {
      dispatch({ type: ACTIONS.SET_VIEW, payload: isFreelancer ? 'browse' : 'projects' });
    }
  }, [isLoggedIn]);

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

  const renderActiveView = () => {
    switch (state.activeView) {
      case 'projects':
        return isEmployer
          ? <EmployerDashboard state={state} dispatch={dispatch} />
          : <FreelancerDashboard state={state} dispatch={dispatch} mode="projects" />;
      case 'browse':
        return <FreelancerDashboard state={state} dispatch={dispatch} mode="browse" />;
      case 'proposals':
        return <FreelancerDashboard state={state} dispatch={dispatch} mode="proposals" />;
      case 'analytics':
        return isEmployer
          ? <AnalyticsPanel state={state} dispatch={dispatch} />
          : <FreelancerDashboard state={state} dispatch={dispatch} mode="projects" />;
      case 'pfi':
        return <PFIDashboard state={state} dispatch={dispatch} mode="self" />;
      case 'leaderboard':
        return <PFIDashboard state={state} dispatch={dispatch} mode="leaderboard" />;
      default:
        return isEmployer
          ? <EmployerDashboard state={state} dispatch={dispatch} />
          : <FreelancerDashboard state={state} dispatch={dispatch} mode="browse" />;
    }
  };

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
          <div className="user-info">
            <span className="user-role-badge">
              {isEmployer ? <Building size={14} className="inline-block mr-1" /> : <User size={14} className="inline-block mr-1" />}
              {state.user.role}
            </span>
            <span className="user-name">{state.user.name}</span>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={handleLogout} title="Sign out" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <LogOut size={16} /> Logout
          </button>
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
                className={`nav-btn ${state.activeView === item.key ? 'active' : ''}`}
                onClick={() => dispatch({ type: ACTIONS.SET_VIEW, payload: item.key })}
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
          {renderActiveView()}
        </main>

        {/* Right Panel: Escrow Ledger */}
        <aside className="ledger-aside">
          <EscrowLedger state={state} dispatch={dispatch} />
        </aside>
      </div>
    </div>
  );
}
