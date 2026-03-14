import React, { useState } from 'react';

export default function AQAReport({ result, milestoneIndex, milestone }) {
  if (!result) return null;

  const [showLayerDetails, setShowLayerDetails] = useState(false);
  const [showDispute, setShowDispute] = useState(false);

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
  const codePipeline = result.codePipeline || null;

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

      {/* ═══ CODE PIPELINE SECTION ═══ */}
      {codePipeline && (
        <div className="code-pipeline-section">
          {/* Repo Info Bar */}
          <div className="pipeline-repo-info">
            <span className="pipeline-label">🔬 Code Verification Pipeline</span>
            <div className="pipeline-repo-meta">
              <a href={codePipeline.repoUrl} target="_blank" rel="noopener noreferrer" className="repo-link">
                🔗 {codePipeline.repoUrl?.replace('https://github.com/', '')}
              </a>
              {codePipeline.commitHash && codePipeline.commitHash !== 'unknown' && (
                <span className="commit-badge mono" title={codePipeline.commitHash}>
                  #{codePipeline.commitHash.slice(0, 7)}
                </span>
              )}
              <span className="lang-badge">{codePipeline.language}</span>
            </div>
          </div>

          {/* Layer Score Cards */}
          <div className="layer-score-cards">
            {[
              { key: 'static', label: 'Static (AST)', weight: '15%', icon: '🏗️' },
              { key: 'runtime', label: 'Runtime Tests', weight: '35%', icon: '▶️' },
              { key: 'sonarqube', label: 'SonarQube', weight: '20%', icon: '🛡️' },
              { key: 'llm', label: 'LLM Semantic', weight: '30%', icon: '🧠' },
            ].map(layer => {
              const score = codePipeline.layerScores?.[layer.key] ?? 0;
              return (
                <div key={layer.key} className="layer-score-card">
                  <div className="layer-card-header">
                    <span className="layer-icon">{layer.icon}</span>
                    <span className="layer-name">{layer.label}</span>
                    <span className="layer-weight">{layer.weight}</span>
                  </div>
                  <div className="layer-score-value" style={{ color: scoreColor(score) }}>
                    {Math.round(score)}
                  </div>
                  <div className="layer-score-bar">
                    <div
                      className="layer-score-bar-fill"
                      style={{ width: `${score}%`, background: scoreColor(score) }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Expandable Layer Details */}
          <button
            className="btn btn-sm btn-ghost layer-details-toggle"
            onClick={() => setShowLayerDetails(!showLayerDetails)}
          >
            {showLayerDetails ? '▲ Hide' : '▼ Show'} Layer Details
          </button>

          {showLayerDetails && codePipeline.layerDetails && (
            <div className="layer-details-grid">
              {Object.entries(codePipeline.layerDetails).map(([layerName, details]) => {
                if (!details || Object.keys(details).length === 0) return null;
                return (
                  <div key={layerName} className="layer-detail-block">
                    <h6 className="layer-detail-title">
                      {layerName === 'static' ? '🏗️' : layerName === 'runtime' ? '▶️' : layerName === 'sonarqube' ? '🛡️' : layerName === 'security' ? '🔒' : '📦'}
                      {' '}{layerName.charAt(0).toUpperCase() + layerName.slice(1)}
                    </h6>
                    {Object.entries(details).map(([key, detail]) => (
                      <div key={key} className="layer-detail-item">
                        <span className="layer-detail-key">{key.replace(/_/g, ' ')}</span>
                        <span className="layer-detail-val">{detail}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          )}

          {/* Security Issues */}
          {codePipeline.securityIssues && codePipeline.securityIssues.length > 0 && (
            <div className="security-issues-section">
              <h6>🔒 Security Issues ({codePipeline.securityIssues.length})</h6>
              <ul className="security-issues-list">
                {codePipeline.securityIssues.map((issue, i) => (
                  <li key={i} className="security-issue-item">⚠ {issue}</li>
                ))}
              </ul>
            </div>
          )}

          {/* PFI Signals */}
          {codePipeline.pfiSignals && (
            <div className="pfi-signals-row">
              <span className="pfi-signal">
                ✅ Tests: {((codePipeline.pfiSignals.auto_tests_passed_ratio || 0) * 100).toFixed(0)}%
              </span>
              {codePipeline.pfiSignals.security_issues > 0 && (
                <span className="pfi-signal pfi-signal-warn">
                  🔒 Security: {codePipeline.pfiSignals.security_issues} issue{codePipeline.pfiSignals.security_issues !== 1 ? 's' : ''}
                </span>
              )}
              <span className="pfi-signal">
                🛡️ SonarQube: {codePipeline.pfiSignals.sonarqube_available ? 'Active' : 'N/A'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Score Split: Deterministic vs LLM (standard non-pipeline view) */}
      {!codePipeline && modalityScores.deterministic && Object.keys(modalityScores.deterministic).length > 0 && (
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

      {/* Code pipeline weighted score breakdown */}
      {codePipeline && modalityScores.weights && (
        <div className="score-split-section">
          <h6>📊 Weighted Score Breakdown</h6>
          <div className="score-split-grid">
            <div className="score-split-col">
              <span className="score-split-label">Deterministic Layers</span>
              {Object.entries(modalityScores.deterministic || {}).map(([key, val]) => (
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
                <span className="score-split-label">LLM Semantic (30%)</span>
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

      {/* Dispute Evidence (collapsible) */}
      {result.disputeEvidence && (
        <div className="dispute-evidence-section">
          <button
            className="btn btn-sm btn-ghost dispute-toggle"
            onClick={() => setShowDispute(!showDispute)}
          >
            📋 {showDispute ? 'Hide' : 'Show'} Dispute Evidence
          </button>
          {showDispute && (
            <pre className="dispute-evidence-block">{result.disputeEvidence}</pre>
          )}
        </div>
      )}
    </div>
  );
}
