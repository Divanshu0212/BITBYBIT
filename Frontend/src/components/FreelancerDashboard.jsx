import React, { useState } from 'react';
import { ACTIONS } from '../store/actions';
import { evaluateSubmission } from '../geminiApi';
import { EscrowContract } from '../EscrowContract';
import AQAReport from './AQAReport';

export default function FreelancerDashboard({ state, dispatch }) {
  const [selectedMs, setSelectedMs] = useState(null);
  const [submissionText, setSubmissionText] = useState('');
  const [submissionUrl, setSubmissionUrl] = useState('');

  const escrow = state.escrow;
  const milestones = escrow?.milestones || [];

  if (!escrow) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>👩‍💻 Freelancer Dashboard</h2>
        </div>
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>No Active Project</h3>
          <p>An employer needs to create and fund a project first.</p>
          <button className="btn btn-ghost" onClick={() =>
            dispatch({ type: ACTIONS.SET_VIEW, payload: 'employer' })
          }>Go to Employer Dashboard →</button>
        </div>
      </div>
    );
  }

  const handleActivate = (index) => {
    try {
      const contract = EscrowContract.fromJSON(escrow);
      contract.activateMilestone(index);
      const newState = contract.getState();
      dispatch({ type: ACTIONS.SET_ESCROW, payload: newState });
      dispatch({ type: ACTIONS.APPEND_LEDGER, payload: newState.ledger.slice(state.ledger.length) });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { freelancer: err.message } });
    }
  };

  const handleSubmitWork = async (index) => {
    if (!submissionText.trim()) return;
    const ms = milestones[index];
    const fullSubmission = submissionText + (submissionUrl ? `\n\nURL: ${submissionUrl}` : '');

    // Update escrow to WORK_SUBMITTED
    try {
      let contract = EscrowContract.fromJSON(escrow);
      contract.submitWork(index, fullSubmission);
      let newState = contract.getState();
      dispatch({ type: ACTIONS.SET_ESCROW, payload: newState });
      dispatch({ type: ACTIONS.APPEND_LEDGER, payload: newState.ledger.slice(state.ledger.length) });

      // Set to AQA_REVIEW
      contract = EscrowContract.fromJSON(newState);
      contract.setAqaReview(index);
      newState = contract.getState();
      dispatch({ type: ACTIONS.SET_ESCROW, payload: newState });
      dispatch({ type: ACTIONS.APPEND_LEDGER, payload: newState.ledger.slice(state.ledger.length) });

      // Call AI evaluation
      dispatch({ type: ACTIONS.SET_LOADING, payload: { aqa: true } });
      const aqaResult = await evaluateSubmission(ms, fullSubmission, state.apiKey);
      dispatch({ type: ACTIONS.SET_AQA_RESULT, payload: { index, result: aqaResult } });

      // Auto-action based on score
      contract = EscrowContract.fromJSON(newState);
      if (aqaResult.overallScore >= 60) {
        const pct = aqaResult.paymentRecommendation === 'FULL_RELEASE'
          ? 100 : (aqaResult.proRatedPercentage || aqaResult.percentComplete || 60);
        contract.releasePayment(index, pct);
      } else if (aqaResult.overallScore < 40) {
        contract.initiateRefund(index, `AQA score: ${aqaResult.overallScore}/100 — ${aqaResult.completionStatus}`);
      } else {
        // 40-60 range: push to HITL queue
        dispatch({
          type: ACTIONS.PUSH_HITL,
          payload: { milestoneIndex: index, milestone: ms, aqaResult, submission: fullSubmission },
        });
      }
      const finalState = contract.getState();
      dispatch({ type: ACTIONS.SET_ESCROW, payload: finalState });
      dispatch({ type: ACTIONS.APPEND_LEDGER, payload: finalState.ledger.slice(state.ledger.length) });

      setSubmissionText('');
      setSubmissionUrl('');
      setSelectedMs(null);
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { aqa: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { aqa: false } });
    }
  };

  const statusIcon = (status) => {
    const icons = {
      PENDING: '⏳',
      IN_PROGRESS: '🔨',
      WORK_SUBMITTED: '📤',
      AQA_REVIEW: '🔍',
      PAID_FULL: '✅',
      PAID_PARTIAL: '⚠️',
      REFUND_INITIATED: '🔄',
    };
    return icons[status] || '📌';
  };

  const statusClass = (status) => {
    if (['PAID_FULL'].includes(status)) return 'status-success';
    if (['PAID_PARTIAL'].includes(status)) return 'status-warning';
    if (['REFUND_INITIATED'].includes(status)) return 'status-danger';
    if (['IN_PROGRESS', 'WORK_SUBMITTED', 'AQA_REVIEW'].includes(status)) return 'status-active';
    return 'status-pending';
  };

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>👩‍💻 Freelancer Dashboard</h2>
        <p className="panel-subtitle">
          Project: {escrow.projectId} • Freelancer: {escrow.freelancerId}
        </p>
      </div>

      {state.errors.freelancer && (
        <div className="error-msg">❌ {state.errors.freelancer}</div>
      )}
      {state.errors.aqa && (
        <div className="error-msg">❌ {state.errors.aqa}</div>
      )}

      <div className="milestone-list">
        {milestones.map((ms, i) => (
          <div key={i} className={`freelancer-ms-card ${statusClass(ms.status)}`}>
            <div className="fms-header">
              <span className="ms-index">M{i + 1}</span>
              <h4>{ms.title}</h4>
              <span className={`status-badge ${statusClass(ms.status)}`}>
                {statusIcon(ms.status)} {ms.status.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="fms-body">
              <div className="fms-meta">
                <span className="domain-tag">{ms.domain}</span>
                <span className="mono">💵 ${ms.paymentAmount?.toLocaleString()}</span>
                <span>⏱ {ms.estimatedDays} days</span>
              </div>
              <div className="criteria-list">
                <strong>Acceptance Criteria:</strong>
                <ul>
                  {(ms.acceptanceCriteria || []).map((c, j) => (
                    <li key={j}>{c}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="fms-actions">
              {ms.status === 'PENDING' && (
                <button className="btn btn-accent" onClick={() => handleActivate(i)}>
                  ▶ Activate Milestone
                </button>
              )}
              {ms.status === 'IN_PROGRESS' && (
                <button className="btn btn-primary" onClick={() => setSelectedMs(i)}>
                  📝 Submit Work
                </button>
              )}
            </div>

            {/* Submission Form */}
            {selectedMs === i && ms.status === 'IN_PROGRESS' && (
              <div className="submission-form animate-fade-in">
                <h5>Submit Work for Review</h5>
                <textarea
                  className="input-textarea"
                  rows={4}
                  value={submissionText}
                  onChange={e => setSubmissionText(e.target.value)}
                  placeholder="Describe the work you've completed in detail..."
                />
                <input
                  type="url"
                  className="input-field"
                  value={submissionUrl}
                  onChange={e => setSubmissionUrl(e.target.value)}
                  placeholder="Optional: Link to deliverable (URL)"
                />
                <div className="btn-row">
                  <button className="btn btn-ghost" onClick={() => setSelectedMs(null)}>Cancel</button>
                  <button
                    className="btn btn-primary"
                    onClick={() => handleSubmitWork(i)}
                    disabled={!submissionText.trim() || state.loading.aqa}
                  >
                    {state.loading.aqa ? <><span className="spinner" /> Running AQA Analysis...</> : '🚀 Submit for AQA Review'}
                  </button>
                </div>
              </div>
            )}

            {/* AQA Results */}
            {state.aqaResults[i] && (
              <AQAReport result={state.aqaResults[i]} milestoneIndex={i} milestone={ms} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
