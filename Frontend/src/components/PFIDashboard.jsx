import React, { useEffect, useState } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';

function GaugeCircle({ score, size = 120 }) {
  const radius = (size - 12) / 2;
  const circumference = Math.PI * radius; // Semi-circle!
  const percentage = Math.max(0, Math.min(1, (score - 300) / 700));
  const offset = circumference - percentage * circumference;
  const color = score >= 850 ? 'var(--cyan)' : score >= 720 ? 'var(--green)' : score >= 580 ? 'var(--yellow)' : score >= 450 ? '#f97316' : 'var(--red)';

  return (
    <svg width={size} height={size / 1.7} className="gauge-svg">
      <path
        d={`M 6,${size/2} A ${radius},${radius} 0 0,1 ${size-6},${size/2}`}
        fill="none"
        stroke="var(--surface-alt)"
        strokeWidth="6"
        strokeLinecap="round" />
      <path
        d={`M 6,${size/2} A ${radius},${radius} 0 0,1 ${size-6},${size/2}`}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="gauge-fill"
      />
      <text x={size / 2} y={size / 2 - 8} textAnchor="middle" fill={color}
        fontSize="24" fontWeight="700" fontFamily="'JetBrains Mono', monospace">
        {score}
      </text>
      <text x={size / 2} y={size / 2 + 10} textAnchor="middle" fill="var(--muted)"
        fontSize="10">
        PFI RANGE
      </text>
    </svg>
  );
}

function Sparkline({ data, width = 120, height = 30 }) {
  if (!data || data.length < 2) return <span className="text-muted mono">No data</span>;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const points = data.map((v, i) =>
    `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * height}`
  ).join(' ');

  return (
    <svg width={width} height={height} className="sparkline-svg">
      <polyline points={points} fill="none" stroke="var(--cyan)" strokeWidth="1.5" />
      {data.map((v, i) => (
        <circle key={i}
          cx={(i / (data.length - 1)) * width}
          cy={height - ((v - min) / range) * height}
          r="2" fill="var(--cyan)"
        />
      ))}
    </svg>
  );
}

export default function PFIDashboard({ state, dispatch, mode = 'self' }) {
  const [loading, setLoading] = useState(false);
  const isFreelancer = state.user?.role === 'freelancer';

  useEffect(() => {
    if (mode === 'self' && isFreelancer) {
      loadOwnPFI();
    }
    if (mode === 'leaderboard') {
      loadLeaderboard();
    }
  }, [mode]);

  const loadOwnPFI = async () => {
    setLoading(true);
    try {
      const [score, history] = await Promise.all([
        api.getOwnPFI(),
        api.getOwnPFIHistory(),
      ]);
      dispatch({ type: ACTIONS.SET_PFI_SCORE, payload: score });
      dispatch({ type: ACTIONS.SET_PFI_HISTORY, payload: history });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { pfi: err.message } });
    } finally {
      setLoading(false);
    }
  };

  const loadLeaderboard = async () => {
    setLoading(true);
    try {
      const data = await api.getLeaderboard();
      dispatch({ type: ACTIONS.SET_LEADERBOARD, payload: data });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { leaderboard: err.message } });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header"><h2>📊 PFI Dashboard</h2></div>
        <div className="empty-state"><span className="spinner" /> Loading...</div>
      </div>
    );
  }

  // Self view (freelancer only)
  if (mode === 'self') {
    const pfi = state.pfiScore;
    const history = state.pfiHistory || [];

    if (!pfi) {
      return (
        <div className="dashboard-panel">
          <div className="panel-header"><h2>📊 My PFI Score</h2></div>
          <div className="empty-state">
            <div className="empty-icon">📊</div>
            <h3>No PFI Data</h3>
            <p>Complete milestones to build your Professional Fidelity Index.</p>
          </div>
        </div>
      );
    }

    const historyScores = history.map(h => h.score);

    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>📊 My Professional Fidelity Index</h2>
          <button className="btn btn-sm btn-ghost" onClick={loadOwnPFI}>🔄 Refresh</button>
        </div>

        <div className="pfi-cards">
          <div className="pfi-card pfi-card-main">
            <div className="pfi-card-top">
              <GaugeCircle score={pfi.score} size={120} />
              <div className="pfi-info">
                <h4>{state.user?.name}</h4>
                <span className={`risk-badge risk-${(pfi.risk || 'unproven').toLowerCase().replace(/\s/g, '-')}`}>
                  {pfi.risk}
                </span>
              </div>
            </div>
            <div className="pfi-metrics">
              <div className="metric">
                <span className="metric-label">Score Range</span>
                <span className="metric-value mono">300 - 1000</span>
              </div>
              <div className="metric">
                <span className="metric-label">Score History</span>
                <Sparkline data={historyScores} />
              </div>
            </div>
          </div>
        </div>

        {/* History Table */}
        {history.length > 0 && (
          <div className="chart-section">
            <h3>📜 Score History</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Event</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i}>
                    <td className="mono">{new Date(h.timestamp).toLocaleDateString()}</td>
                    <td>{h.event_type.replace(/_/g, ' ')}</td>
                    <td className="mono" style={{ color: h.score >= 720 ? 'var(--green)' : h.score >= 580 ? 'var(--yellow)' : h.score >= 450 ? '#f97316' : 'var(--red)' }}>{h.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  // Leaderboard view (both roles)
  const sorted = state.leaderboard || [];

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>🏆 PFI Leaderboard</h2>
        <button className="btn btn-sm btn-ghost" onClick={loadLeaderboard}>🔄 Refresh</button>
      </div>

      {state.errors.leaderboard && (
        <div className="error-msg">❌ {state.errors.leaderboard}</div>
      )}

      {sorted.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🏆</div>
          <h3>No Scores Yet</h3>
          <p>Freelancers need to complete milestones to appear on the leaderboard.</p>
        </div>
      ) : (
        <div className="leaderboard">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Freelancer</th>
                <th>PFI Score</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((fl, i) => (
                <tr key={fl.user_id}>
                  <td className="mono">{i + 1}</td>
                  <td>{fl.user_id}</td>
                  <td className="mono" style={{
                    color: fl.score >= 720 ? 'var(--green)' : fl.score >= 580 ? 'var(--yellow)' : fl.score >= 450 ? '#f97316' : 'var(--red)'
                  }}>
                    {fl.score}
                  </td>
                  <td>
                    <span className={`risk-badge risk-${(fl.risk || 'unproven').toLowerCase().replace(/\s/g, '-')}`}>
                      {fl.risk}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
