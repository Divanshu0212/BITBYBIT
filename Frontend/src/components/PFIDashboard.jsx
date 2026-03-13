import React from 'react';
import {
  calculateBaseScore,
  applyGlicko2,
  computeFinalPFI,
  getConfidenceLabel,
  getRiskLabel,
} from '../pfiCalculator';

function GaugeCircle({ score, size = 100 }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--yellow)' : 'var(--red)';

  return (
    <svg width={size} height={size} className="gauge-svg">
      <circle cx={size / 2} cy={size / 2} r={radius}
        fill="none" stroke="var(--surface-alt)" strokeWidth="6" />
      <circle cx={size / 2} cy={size / 2} r={radius}
        fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className="gauge-fill"
      />
      <text x={size / 2} y={size / 2 - 6} textAnchor="middle" fill={color}
        fontSize="20" fontWeight="700" fontFamily="'JetBrains Mono', monospace">
        {score}
      </text>
      <text x={size / 2} y={size / 2 + 12} textAnchor="middle" fill="var(--muted)"
        fontSize="10">
        PFI
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

export default function PFIDashboard({ state }) {
  const { freelancers, pfiScores, aqaResults, escrow } = state;

  // Build freelancer PFI data dynamically
  const pfiData = freelancers.map(fl => {
    const scores = pfiScores[fl.id] || {};
    const aqaScoresArr = Object.values(aqaResults).map(r => r.overallScore).filter(Boolean);

    const history = {
      completedMilestones: escrow?.milestones?.filter(m =>
        ['PAID_FULL', 'PAID_PARTIAL'].includes(m.status)
      ).length || 0,
      totalMilestones: escrow?.milestones?.length || 1,
      onTimeDeliveries: escrow?.milestones?.filter(m =>
        ['PAID_FULL'].includes(m.status)
      ).length || 0,
      totalDeliveries: escrow?.milestones?.filter(m =>
        ['PAID_FULL', 'PAID_PARTIAL', 'REFUND_INITIATED'].includes(m.status)
      ).length || 0,
      aqaScores: aqaScoresArr,
      disputes: escrow?.milestones?.filter(m =>
        m.status === 'REFUND_INITIATED'
      ).length || 0,
      totalJobs: escrow?.milestones?.filter(m =>
        m.status !== 'PENDING'
      ).length || 0,
    };

    const baseScore = calculateBaseScore(history);
    const glicko = applyGlicko2(
      scores.rating || 1500,
      scores.RD || 350,
      scores.volatility || 0.06,
      aqaScoresArr.map(s => ({ score: s / 100, expected: 0.5 }))
    );
    const finalPFI = computeFinalPFI(baseScore, glicko.rating);
    const confidence = getConfidenceLabel(glicko.RD);
    const risk = getRiskLabel(finalPFI);

    return {
      ...fl,
      baseScore,
      glicko,
      finalPFI,
      confidence,
      risk,
      history: scores.history || aqaScoresArr,
    };
  });

  // Sort for leaderboard
  const sorted = [...pfiData].sort((a, b) => b.finalPFI - a.finalPFI);

  if (freelancers.length === 0) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>📊 PFI Dashboard</h2>
        </div>
        <div className="empty-state">
          <div className="empty-icon">👥</div>
          <h3>No Freelancers</h3>
          <p>Generate a demo project to add freelancers, or complete milestones to build PFI scores.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>📊 Platform Freelancer Index</h2>
        <p className="panel-subtitle">Glicko-2 powered reputation scoring with bias detection</p>
      </div>

      <div className="pfi-cards">
        {pfiData.map(fl => (
          <div key={fl.id} className="pfi-card">
            <div className="pfi-card-top">
              <GaugeCircle score={fl.finalPFI} size={90} />
              <div className="pfi-info">
                <h4>{fl.name}</h4>
                <div className="pfi-tags">
                  {fl.skills?.map((s, i) => (
                    <span key={i} className="skill-tag">{s}</span>
                  ))}
                </div>
                <span className={`risk-badge risk-${fl.risk.toLowerCase().replace(/\s/g, '-')}`}>
                  {fl.risk}
                </span>
              </div>
            </div>
            <div className="pfi-metrics">
              <div className="metric">
                <span className="metric-label">Rating</span>
                <span className="metric-value mono">{fl.glicko.rating}</span>
              </div>
              <div className="metric">
                <span className="metric-label">RD</span>
                <div className="rd-bar">
                  <div className="rd-bar-fill" style={{ width: `${Math.min(fl.glicko.RD / 350 * 100, 100)}%` }} />
                </div>
                <span className="metric-sub">{fl.confidence} confidence</span>
              </div>
              <div className="metric">
                <span className="metric-label">Volatility</span>
                <Sparkline data={fl.history} />
              </div>
              <div className="metric">
                <span className="metric-label">Base Score</span>
                <span className="metric-value mono">{fl.baseScore}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Leaderboard */}
      {sorted.length > 0 && (
        <div className="leaderboard">
          <h3>🏆 Leaderboard</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Freelancer</th>
                <th>PFI Score</th>
                <th>Glicko Rating</th>
                <th>Confidence</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((fl, i) => (
                <tr key={fl.id}>
                  <td className="mono">{i + 1}</td>
                  <td>{fl.name}</td>
                  <td className="mono" style={{ color: fl.finalPFI >= 70 ? 'var(--green)' : fl.finalPFI >= 40 ? 'var(--yellow)' : 'var(--red)' }}>
                    {fl.finalPFI}
                  </td>
                  <td className="mono">{fl.glicko.rating}</td>
                  <td>{fl.confidence}</td>
                  <td>
                    <span className={`risk-badge risk-${fl.risk.toLowerCase().replace(/\s/g, '-')}`}>
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
