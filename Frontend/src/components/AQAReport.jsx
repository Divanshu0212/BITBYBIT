import React from 'react';

export default function AQAReport({ result, milestoneIndex, milestone }) {
  if (!result) return null;

  const scoreColor = (score) => {
    if (score >= 80) return 'var(--green)';
    if (score >= 60) return 'var(--yellow)';
    if (score >= 40) return 'var(--orange)';
    return 'var(--red)';
  };

  const statusBadgeClass = (status) => {
    if (status === 'FULLY_COMPLETED') return 'status-success';
    if (status === 'PARTIALLY_COMPLETED') return 'status-warning';
    return 'status-danger';
  };

  const paymentBadge = (rec) => {
    if (rec === 'FULL_RELEASE') return { icon: '✅', cls: 'status-success', label: 'Full Release' };
    if (rec === 'PRO_RATED') return { icon: '⚠️', cls: 'status-warning', label: 'Pro-Rated' };
    return { icon: '🔄', cls: 'status-danger', label: 'Refund' };
  };

  const pb = paymentBadge(result.paymentRecommendation);

  return (
    <div className="aqa-report animate-fade-in">
      <div className="aqa-header">
        <h5>🔍 AQA Analysis — M{milestoneIndex + 1}</h5>
        <div className="aqa-score-circle" style={{ borderColor: scoreColor(result.overallScore) }}>
          <span className="score-value" style={{ color: scoreColor(result.overallScore) }}>
            {result.overallScore}
          </span>
          <span className="score-label">/100</span>
        </div>
      </div>

      <div className="aqa-badges">
        <span className={`status-badge ${statusBadgeClass(result.completionStatus)}`}>
          {result.completionStatus?.replace(/_/g, ' ')}
        </span>
        <span className={`status-badge ${pb.cls}`}>
          {pb.icon} {pb.label}
        </span>
        <span className="meta-tag mono">{result.percentComplete}% complete</span>
      </div>

      {/* Criteria Breakdown */}
      <div className="criteria-eval">
        {(result.criteriaEvaluation || []).map((ce, i) => (
          <div key={i} className="crit-row">
            <div className="crit-header">
              <span className={`crit-status ${ce.met ? 'met' : 'unmet'}`}>
                {ce.met ? '✅' : '❌'}
              </span>
              <span className="crit-text">{ce.criterion}</span>
              <span className="crit-score mono" style={{ color: scoreColor(ce.score) }}>
                {ce.score}/100
              </span>
            </div>
            <div className="crit-bar">
              <div
                className="crit-bar-fill"
                style={{ width: `${ce.score}%`, background: scoreColor(ce.score) }}
              />
            </div>
            <div className="crit-feedback">{ce.feedback}</div>
          </div>
        ))}
      </div>

      {result.detailedFeedback && (
        <div className="aqa-feedback">
          <strong>Detailed Feedback:</strong>
          <p>{result.detailedFeedback}</p>
        </div>
      )}
    </div>
  );
}
