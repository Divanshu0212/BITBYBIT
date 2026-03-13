import React, { useEffect, useState } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';

export default function AnalyticsPanel({ state, dispatch }) {
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      const data = await api.getEmployerAnalytics();
      dispatch({ type: ACTIONS.SET_ANALYTICS, payload: data });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { analytics: err.message } });
    } finally {
      setLoading(false);
    }
  };

  const analytics = state.analytics;

  if (loading) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header"><h2>📈 Analytics</h2></div>
        <div className="empty-state"><span className="spinner" /> Loading analytics...</div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header"><h2>📈 Analytics</h2></div>
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h3>No Data Yet</h3>
          <p>Create a project and complete milestones to see analytics.</p>
        </div>
      </div>
    );
  }

  const funnelData = [
    { label: 'Activated', count: analytics.funnel?.activated || 0 },
    { label: 'Submitted', count: analytics.funnel?.submitted || 0 },
    { label: 'AQA Passed', count: analytics.funnel?.aqaPassed || 0 },
    { label: 'Paid', count: analytics.funnel?.paid || 0 },
  ];
  const maxFunnel = Math.max(...funnelData.map(f => f.count), 1);

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>📈 Analytics</h2>
        <button className="btn btn-sm btn-ghost" onClick={loadAnalytics}>🔄 Refresh</button>
      </div>

      {state.errors.analytics && (
        <div className="error-msg">❌ {state.errors.analytics}</div>
      )}

      {/* Summary Row */}
      <div className="analytics-summary">
        <div className="summary-card">
          <div className="summary-value mono">{analytics.totalProjects}</div>
          <div className="summary-label">Total Projects</div>
        </div>
        <div className="summary-card">
          <div className="summary-value mono cyan">${(analytics.totalInEscrow || 0).toLocaleString()}</div>
          <div className="summary-label">In Escrow</div>
        </div>
        <div className="summary-card">
          <div className="summary-value mono green">${(analytics.totalReleased || 0).toLocaleString()}</div>
          <div className="summary-label">Released</div>
        </div>
        <div className="summary-card">
          <div className="summary-value mono red">${(analytics.totalRefunded || 0).toLocaleString()}</div>
          <div className="summary-label">Refunded</div>
        </div>
        <div className="summary-card">
          <div className="summary-value mono">{analytics.totalMilestones}</div>
          <div className="summary-label">Total Milestones</div>
        </div>
      </div>

      {/* Milestone Funnel */}
      <div className="chart-section">
        <h3>Milestone Funnel</h3>
        <div className="funnel-chart">
          {funnelData.map((f, i) => (
            <div key={i} className="funnel-row">
              <span className="funnel-label">{f.label}</span>
              <div className="funnel-bar-container">
                <div className="funnel-bar"
                  style={{ width: `${(f.count / maxFunnel) * 100}%` }}
                />
              </div>
              <span className="funnel-count mono">{f.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
