import React, { useState } from 'react';
import { ACTIONS } from '../store/actions';
import { EscrowContract } from '../EscrowContract';

export default function HITLOverride({ state, dispatch }) {
  const [reasons, setReasons] = useState({});

  if (state.hitlQueue.length === 0) return null;

  const handleAction = (queueIndex, action) => {
    const item = state.hitlQueue[queueIndex];
    if (!item || !state.escrow) return;

    const contract = EscrowContract.fromJSON(state.escrow);
    const reason = reasons[queueIndex] || '';

    try {
      switch (action) {
        case 'approve':
          // Approve AI decision (which was indeterminate 40-60)
          if (item.aqaResult.paymentRecommendation === 'PRO_RATED') {
            contract.releasePayment(item.milestoneIndex, item.aqaResult.proRatedPercentage || 50);
          } else {
            contract.releasePayment(item.milestoneIndex, item.aqaResult.percentComplete || 50);
          }
          break;
        case 'full_pay':
          contract.releasePayment(item.milestoneIndex, 100);
          break;
        case 'refund':
          contract.initiateRefund(item.milestoneIndex, reason || 'HITL override: refund');
          break;
        case 'resubmit':
          // Reset milestone to IN_PROGRESS for resubmission
          const ms = contract.milestones[item.milestoneIndex];
          if (ms) {
            ms.status = 'IN_PROGRESS';
            ms.submission = null;
            contract.state = 'MILESTONE_ACTIVE';
            contract._log('RESUBMISSION_REQUESTED', null, 'STATE_CHANGE',
              `Resubmission requested for M${item.milestoneIndex + 1}: ${reason || 'HITL override'}`);
          }
          break;
      }

      const newState = contract.getState();
      dispatch({ type: ACTIONS.SET_ESCROW, payload: newState });
      dispatch({ type: ACTIONS.APPEND_LEDGER, payload: newState.ledger.slice(state.ledger.length) });
      dispatch({ type: ACTIONS.RESOLVE_HITL, payload: queueIndex });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { hitl: err.message } });
    }
  };

  return (
    <div className="hitl-panel animate-fade-in">
      <div className="hitl-header">
        <h3>⚖ Human-in-the-Loop Review</h3>
        <span className="hitl-count">{state.hitlQueue.length} pending</span>
      </div>

      {state.errors.hitl && (
        <div className="error-msg">❌ {state.errors.hitl}</div>
      )}

      {state.hitlQueue.map((item, qi) => (
        <div key={qi} className="hitl-card">
          <div className="hitl-card-header">
            <span className="ms-index">M{item.milestoneIndex + 1}</span>
            <h4>{item.milestone.title}</h4>
            <span className="aqa-score-badge" style={{
              background: `hsl(${item.aqaResult.overallScore * 1.2}, 70%, 20%)`,
              color: `hsl(${item.aqaResult.overallScore * 1.2}, 70%, 70%)`
            }}>
              Score: {item.aqaResult.overallScore}/100
            </span>
          </div>

          <div className="hitl-summary">
            <p><strong>AI Recommendation:</strong> {item.aqaResult.paymentRecommendation?.replace(/_/g, ' ')}</p>
            <p><strong>Status:</strong> {item.aqaResult.completionStatus?.replace(/_/g, ' ')}</p>
            <p><strong>Feedback:</strong> {item.aqaResult.detailedFeedback}</p>
          </div>

          <div className="hitl-criteria-summary">
            {(item.aqaResult.criteriaEvaluation || []).map((ce, i) => (
              <span key={i} className={`crit-chip ${ce.met ? 'met' : 'unmet'}`}>
                {ce.met ? '✅' : '❌'} {ce.criterion?.slice(0, 40)}{ce.criterion?.length > 40 ? '…' : ''}
              </span>
            ))}
          </div>

          <div className="hitl-reason">
            <input
              className="input-field"
              placeholder="Override reason (required for Refund/Resubmit)"
              value={reasons[qi] || ''}
              onChange={e => setReasons({ ...reasons, [qi]: e.target.value })}
            />
          </div>

          <div className="hitl-actions">
            <button className="btn btn-sm btn-accent" onClick={() => handleAction(qi, 'approve')}>
              ✅ Approve AI Decision
            </button>
            <button className="btn btn-sm btn-primary" onClick={() => handleAction(qi, 'full_pay')}>
              💰 Override: Full Pay
            </button>
            <button className="btn btn-sm btn-danger" onClick={() => handleAction(qi, 'refund')}
              disabled={!reasons[qi]?.trim()}>
              🔄 Override: Refund
            </button>
            <button className="btn btn-sm btn-ghost" onClick={() => handleAction(qi, 'resubmit')}
              disabled={!reasons[qi]?.trim()}>
              📝 Request Resubmission
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
