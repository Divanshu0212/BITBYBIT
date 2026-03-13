import React, { useState, useEffect } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';

export default function HITLOverride({ state, dispatch }) {
  const [reasons, setReasons] = useState({});
  const [loadingAction, setLoadingAction] = useState(null);

  // Load HITL items for all active projects
  useEffect(() => {
    loadHITL();
  }, [state.projects]);

  const loadHITL = async () => {
    const activeProjects = (state.projects || []).filter(p => p.status === 'active');
    const allItems = [];
    for (const p of activeProjects) {
      try {
        const items = await api.getProjectHITL(p.id);
        allItems.push(...items.map(item => ({ ...item, project_id: p.id })));
      } catch { /* ignore 404s */ }
    }
    dispatch({ type: ACTIONS.SET_HITL_ITEMS, payload: allItems });
  };

  if (!state.hitlItems || state.hitlItems.length === 0) return null;

  const handleAction = async (item, action) => {
    const key = `${item.milestone_id}-${action}`;
    setLoadingAction(key);
    try {
      await api.resolveHITL(
        item.project_id,
        item.milestone_id,
        action,
        reasons[item.milestone_id] || null
      );
      await loadHITL();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { hitl: err.message } });
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="hitl-panel animate-fade-in">
      <div className="hitl-header">
        <h3>⚖ Human-in-the-Loop Review</h3>
        <span className="hitl-count">{state.hitlItems.length} pending</span>
      </div>

      {state.errors.hitl && (
        <div className="error-msg">❌ {state.errors.hitl}</div>
      )}

      {state.hitlItems.map((item, qi) => (
        <div key={item.id || qi} className="hitl-card">
          <div className="hitl-card-header">
            <h4>Milestone Review</h4>
            {item.aqa_result && (
              <span className="aqa-score-badge" style={{
                background: `hsl(${(item.aqa_result.overallScore || 50) * 1.2}, 70%, 20%)`,
                color: `hsl(${(item.aqa_result.overallScore || 50) * 1.2}, 70%, 70%)`
              }}>
                Score: {item.aqa_result.overallScore}/100
              </span>
            )}
          </div>

          {item.aqa_result && (
            <div className="hitl-summary">
              <p><strong>AI Recommendation:</strong> {item.aqa_result.paymentRecommendation?.replace(/_/g, ' ')}</p>
              <p><strong>Status:</strong> {item.aqa_result.completionStatus?.replace(/_/g, ' ')}</p>
              <p><strong>Feedback:</strong> {item.aqa_result.detailedFeedback}</p>
            </div>
          )}

          {item.aqa_result?.criteriaEvaluation && (
            <div className="hitl-criteria-summary">
              {item.aqa_result.criteriaEvaluation.map((ce, i) => (
                <span key={i} className={`crit-chip ${ce.met ? 'met' : 'unmet'}`}>
                  {ce.met ? '✅' : '❌'} {ce.criterion?.slice(0, 40)}{ce.criterion?.length > 40 ? '…' : ''}
                </span>
              ))}
            </div>
          )}

          <div className="hitl-reason">
            <input
              className="input-field"
              placeholder="Override reason (required for Refund/Resubmit)"
              value={reasons[item.milestone_id] || ''}
              onChange={e => setReasons({ ...reasons, [item.milestone_id]: e.target.value })}
            />
          </div>

          <div className="hitl-actions">
            <button className="btn btn-sm btn-accent"
              onClick={() => handleAction(item, 'approve')}
              disabled={!!loadingAction}>
              ✅ Approve AI Decision
            </button>
            <button className="btn btn-sm btn-primary"
              onClick={() => handleAction(item, 'full_pay')}
              disabled={!!loadingAction}>
              💰 Override: Full Pay
            </button>
            <button className="btn btn-sm btn-danger"
              onClick={() => handleAction(item, 'refund')}
              disabled={!!loadingAction || !reasons[item.milestone_id]?.trim()}>
              🔄 Override: Refund
            </button>
            <button className="btn btn-sm btn-ghost"
              onClick={() => handleAction(item, 'resubmit')}
              disabled={!!loadingAction || !reasons[item.milestone_id]?.trim()}>
              📝 Request Resubmission
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
