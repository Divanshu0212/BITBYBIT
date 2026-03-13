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

  const modalityIcon = (m) => {
    if (m === 'code') return '💻';
    if (m === 'content') return '📝';
    if (m === 'design') return '🎨';
    return '🔀';
  };

  const confidenceLabel = (c) => {
    if (c >= 0.85) return { label: 'High', cls: 'confidence-high' };
    if (c >= 0.7) return { label: 'Moderate', cls: 'confidence-moderate' };
    return { label: 'Low', cls: 'confidence-low' };
  };

  const pb = paymentBadge(result.paymentRecommendation);
  const modality = result.modality || 'mixed';
  const confidence = result.confidence ?? 0.5;
  const evidenceCompleteness = result.evidenceCompleteness ?? 0;
  const confInfo = confidenceLabel(confidence);
  const modalityScores = result.modalityScores || {};

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

      {/* Modality + Confidence + Evidence Row */}
      <div className="aqa-meta-row">
        <span className="meta-tag modality-badge" title="Task modality">
          {modalityIcon(modality)} {modality.toUpperCase()}
        </span>
        <span className={`meta-tag ${confInfo.cls}`} title={`Confidence: ${(confidence * 100).toFixed(0)}%`}>
          🎯 {confInfo.label} Confidence ({(confidence * 100).toFixed(0)}%)
        </span>
        <div className="evidence-bar-wrap" title={`Evidence: ${(evidenceCompleteness * 100).toFixed(0)}%`}>
          <span className="evidence-label">📎 Evidence</span>
          <div className="evidence-bar">
            <div
              className="evidence-bar-fill"
              style={{
                width: `${evidenceCompleteness * 100}%`,
                background: evidenceCompleteness >= 0.7 ? 'var(--green)' : evidenceCompleteness >= 0.4 ? 'var(--yellow)' : 'var(--red)',
              }}
            />
          </div>
          <span className="evidence-pct mono">{(evidenceCompleteness * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Status Badges */}
      <div className="aqa-badges">
        <span className={`status-badge ${statusBadgeClass(result.completionStatus)}`}>
          {result.completionStatus?.replace(/_/g, ' ')}
        </span>
        <span className={`status-badge ${pb.cls}`}>
          {pb.icon} {pb.label}
        </span>
        <span className="meta-tag mono">{result.percentComplete}% complete</span>
      </div>

      {/* Score Split: Deterministic vs LLM */}
      {modalityScores.deterministic && Object.keys(modalityScores.deterministic).length > 0 && (
        <div className="score-split-section">
          <h6>📊 Score Breakdown</h6>
          <div className="score-split-grid">
            <div className="score-split-col">
              <span className="score-split-label">Deterministic (30%)</span>
              {Object.entries(modalityScores.deterministic).map(([key, val]) => (
                <div key={key} className="score-split-item">
                  <span className="score-split-key">{key.replace(/_/g, ' ')}</span>
                  <div className="crit-bar mini">
                    <div className="crit-bar-fill" style={{ width: `${val}%`, background: scoreColor(val) }} />
                  </div>
                  <span className="mono score-split-val">{Math.round(val)}</span>
                </div>
              ))}
            </div>
            {modalityScores.llm && Object.keys(modalityScores.llm).length > 0 && (
              <div className="score-split-col">
                <span className="score-split-label">LLM Review (70%)</span>
                {Object.entries(modalityScores.llm).map(([key, val]) => (
                  <div key={key} className="score-split-item">
                    <span className="score-split-key">{key.replace(/_/g, ' ')}</span>
                    <div className="crit-bar mini">
                      <div className="crit-bar-fill" style={{ width: `${val}%`, background: scoreColor(val) }} />
                    </div>
                    <span className="mono score-split-val">{Math.round(val)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Criteria Breakdown */}
      <div className="criteria-eval">
        {(result.criteriaEvaluation || []).map((ce, i) => (
          <div key={i} className="crit-row">
            <div className="crit-header">
              <span className={`crit-status ${ce.met ? 'met' : 'unmet'}`}>
                {ce.met ? '✅' : '❌'}
              </span>
              <span className="crit-text">{ce.criterion}</span>
              {ce.evidence_present !== undefined && (
                <span className={`evidence-indicator ${ce.evidence_present ? 'has-evidence' : 'no-evidence'}`}>
                  {ce.evidence_present ? '📎' : '⚠️'}
                </span>
              )}
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

      {/* Remediation Checklist */}
      {result.remediationChecklist && result.remediationChecklist.length > 0 && (
        <div className="remediation-section">
          <h6>🔧 Remediation Checklist</h6>
          <ul className="remediation-list">
            {result.remediationChecklist.map((item, i) => (
              <li key={i} className="remediation-item">{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Risk Flags */}
      {result.riskFlags && result.riskFlags.length > 0 && (
        <div className="risk-flags-section">
          <h6>⚠️ Risk Flags</h6>
          <div className="risk-flags">
            {result.riskFlags.map((flag, i) => (
              <span key={i} className="risk-flag-badge">{flag}</span>
            ))}
          </div>
        </div>
      )}

      {result.detailedFeedback && (
        <div className="aqa-feedback">
          <strong>Detailed Feedback:</strong>
          <p>{result.detailedFeedback}</p>
        </div>
      )}

      {/* Decision Info */}
      {result.decision && (
        <div className="decision-info">
          <span className="meta-tag mono">
            Decision: {result.decision.action} — {result.decision.reason}
          </span>
        </div>
      )}
    </div>
  );
}
