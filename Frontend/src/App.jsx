import React, { useReducer, useEffect, useState } from 'react';
import { reducer, initialState } from './store/reducer';
import { ACTIONS } from './store/actions';

import SettingsModal from './components/SettingsModal';
import EscrowLedger from './components/EscrowLedger';
import EmployerDashboard from './components/EmployerDashboard';
import FreelancerDashboard from './components/FreelancerDashboard';
import PFIDashboard from './components/PFIDashboard';
import AnalyticsPanel from './components/AnalyticsPanel';
import AgentScorer from './components/AgentScorer';
import HITLOverride from './components/HITLOverride';

const STORAGE_KEY = 'bitbybit_state';

function loadInitialState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      return { ...initialState, ...parsed };
    }
  } catch { /* ignore */ }
  // Also check for API key
  const apiKey = localStorage.getItem('bitbybit_api_key');
  if (apiKey) return { ...initialState, apiKey };
  return initialState;
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, null, loadInitialState);
  const [showSettings, setShowSettings] = useState(!state.apiKey);

  // Persist state to localStorage
  useEffect(() => {
    const { loading, errors, ...persistable } = state;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable));
  }, [state]);

  // Sync apiKey changes
  useEffect(() => {
    if (state.apiKey) {
      localStorage.setItem('bitbybit_api_key', state.apiKey);
      setShowSettings(false);
    }
  }, [state.apiKey]);

  const NAV_ITEMS = [
    { key: 'employer', icon: '🏢', label: 'Employer' },
    { key: 'freelancer', icon: '👩‍💻', label: 'Freelancer' },
    { key: 'pfi', icon: '📊', label: 'PFI Index' },
    { key: 'analytics', icon: '📈', label: 'Analytics' },
  ];

  const handleExport = () => {
    const data = JSON.stringify(state, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bitbybit-export-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleReset = () => {
    if (confirm('Reset all project data? Your API key will be preserved.')) {
      dispatch({ type: ACTIONS.RESET_STATE });
    }
  };

  const renderActiveView = () => {
    switch (state.activeView) {
      case 'employer':
        return <EmployerDashboard state={state} dispatch={dispatch} />;
      case 'freelancer':
        return <FreelancerDashboard state={state} dispatch={dispatch} />;
      case 'pfi':
        return <PFIDashboard state={state} dispatch={dispatch} />;
      case 'analytics':
        return <AnalyticsPanel state={state} dispatch={dispatch} />;
      default:
        return <EmployerDashboard state={state} dispatch={dispatch} />;
    }
  };

  return (
    <div className="app-shell">
      {/* Settings Modal */}
      {showSettings && (
        <SettingsModal
          state={state}
          dispatch={dispatch}
          onClose={() => state.apiKey && setShowSettings(false)}
        />
      )}

      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">BITBYBIT</span>
          </div>
          <span className="logo-tagline">Autonomous AI Project & Payment Intermediary</span>
        </div>
        <div className="header-right">
          <button className="btn btn-sm btn-ghost" onClick={handleExport} title="Export project data">
            📥 Export
          </button>
          <button className="btn btn-sm btn-ghost" onClick={handleReset} title="Reset all data">
            🔄 Reset
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => setShowSettings(true)} title="Settings">
            ⚙ Settings
          </button>
          {state.apiKey && <span className="api-status connected">● Connected</span>}
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
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </button>
            ))}
          </div>
          <div className="sidebar-footer">
            {state.escrow && (
              <div className="sidebar-escrow-mini">
                <div className="mini-state">{state.escrow.state}</div>
                <div className="mini-funds mono">${state.escrow.lockedFunds?.toLocaleString()}</div>
              </div>
            )}
          </div>

          {/* Agent Scorer in sidebar */}
          {state.escrow && state.freelancers.length > 0 && (
            <AgentScorer state={state} dispatch={dispatch} />
          )}
        </nav>

        {/* Center Content */}
        <main className="main-content">
          {/* HITL Override banner at top */}
          <HITLOverride state={state} dispatch={dispatch} />
          {renderActiveView()}
        </main>

        {/* Right Panel: Escrow Ledger */}
        <aside className="ledger-aside">
          <EscrowLedger ledger={state.ledger} escrow={state.escrow} />
        </aside>
      </div>
    </div>
  );
}
