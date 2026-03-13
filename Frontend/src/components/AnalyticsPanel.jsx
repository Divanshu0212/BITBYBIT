import React from 'react';

export default function AnalyticsPanel({ state }) {
  const { escrow, ledger, aqaResults, freelancers, pfiScores } = state;
  const milestones = escrow?.milestones || [];

  // --- Summary stats ---
  const activeProjects = state.projects.length;
  const totalInEscrow = escrow?.lockedFunds || 0;
  const aqaScores = Object.values(aqaResults).map(r => r.overallScore).filter(Boolean);
  const avgAqa = aqaScores.length > 0
    ? Math.round(aqaScores.reduce((a, b) => a + b, 0) / aqaScores.length)
    : 0;

  // --- Milestone Funnel ---
  const funnelData = [
    { label: 'Activated', count: milestones.filter(m => m.status !== 'PENDING').length },
    { label: 'Submitted', count: milestones.filter(m =>
      ['WORK_SUBMITTED', 'AQA_REVIEW', 'PAID_FULL', 'PAID_PARTIAL', 'REFUND_INITIATED'].includes(m.status)
    ).length },
    { label: 'AQA Passed', count: milestones.filter(m =>
      ['PAID_FULL', 'PAID_PARTIAL'].includes(m.status)
    ).length },
    { label: 'Paid', count: milestones.filter(m =>
      ['PAID_FULL'].includes(m.status)
    ).length },
  ];
  const maxFunnel = Math.max(...funnelData.map(f => f.count), 1);

  // --- PFI Histogram ---
  const pfiValues = freelancers.map(fl => {
    const s = pfiScores[fl.id];
    return s?.score || 50;
  });
  const histBuckets = Array(10).fill(0);
  pfiValues.forEach(v => {
    const bucket = Math.min(Math.floor(v / 10), 9);
    histBuckets[bucket]++;
  });
  const maxHist = Math.max(...histBuckets, 1);

  // --- Ledger timeline ---
  const typeColors = {
    DEPOSIT: 'var(--cyan)',
    PAYMENT: 'var(--green)',
    REFUND: 'var(--red)',
    STATE_CHANGE: 'var(--muted)',
  };

  if (!escrow && ledger.length === 0) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>📈 Analytics</h2>
        </div>
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h3>No Data Yet</h3>
          <p>Create a project and complete milestones to see analytics.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>📈 Analytics</h2>
        <p className="panel-subtitle">Real-time project metrics — all values computed live from state</p>
      </div>

      {/* Summary Row */}
      <div className="analytics-summary">
        <div className="summary-card">
          <div className="summary-value mono">{activeProjects}</div>
          <div className="summary-label">Active Projects</div>
        </div>
        <div className="summary-card">
          <div className="summary-value mono cyan">${totalInEscrow.toLocaleString()}</div>
          <div className="summary-label">In Escrow</div>
        </div>
        <div className="summary-card">
          <div className="summary-value mono">{avgAqa}</div>
          <div className="summary-label">Avg AQA Score</div>
        </div>
        <div className="summary-card">
          <div className="summary-value mono">{milestones.length}</div>
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

      {/* PFI Histogram */}
      {freelancers.length > 0 && (
        <div className="chart-section">
          <h3>PFI Score Distribution</h3>
          <div className="histogram">
            {histBuckets.map((count, i) => (
              <div key={i} className="hist-col">
                <div className="hist-bar"
                  style={{ height: `${(count / maxHist) * 80}px` }}
                />
                <span className="hist-label mono">{i * 10}-{i * 10 + 9}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Escrow Timeline */}
      {ledger.length > 0 && (
        <div className="chart-section">
          <h3>Escrow Timeline</h3>
          <div className="timeline">
            {ledger.map((entry, i) => (
              <div key={i} className="timeline-event">
                <div className="timeline-dot" style={{ background: typeColors[entry.type] || 'var(--muted)' }} />
                <div className="timeline-connector" />
                <div className="timeline-content">
                  <span className="timeline-label" style={{ color: typeColors[entry.type] }}>
                    {entry.event}
                  </span>
                  {entry.amount != null && (
                    <span className="timeline-amount mono">${entry.amount.toLocaleString()}</span>
                  )}
                  <span className="timeline-time mono">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
