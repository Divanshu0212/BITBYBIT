import React, { useState } from 'react';
import { ACTIONS } from '../store/actions';
import { scoreFreelancerMatch } from '../geminiApi';

export default function AgentScorer({ state, dispatch }) {
  const [loading, setLoading] = useState(false);
  const { freelancers, assignScores, escrow, pfiScores } = state;

  // Get the primary domain of the project
  const projectDomain = escrow?.milestones?.[0]?.domain || 'General';

  const handleScore = async () => {
    if (!state.apiKey || freelancers.length === 0) return;
    setLoading(true);
    try {
      const scores = [];
      for (const fl of freelancers) {
        const result = await scoreFreelancerMatch(fl.skills, projectDomain, state.apiKey);
        const pfi = pfiScores[fl.id]?.score || 50;
        const domainMatch = result.score || 0.5;
        const totalScore = 0.6 * domainMatch + 0.4 * (pfi / 100);
        scores.push({
          freelancerId: fl.id,
          name: fl.name,
          skills: fl.skills,
          domainMatch: Math.round(domainMatch * 100),
          pfiScore: pfi,
          totalScore: Math.round(totalScore * 100),
          reasoning: result.reasoning || '',
        });
      }
      scores.sort((a, b) => b.totalScore - a.totalScore);
      dispatch({ type: ACTIONS.SET_ASSIGN_SCORES, payload: scores });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { scorer: err.message } });
    } finally {
      setLoading(false);
    }
  };

  const handleAssign = (freelancerId, name) => {
    if (!escrow) return;
    const updated = { ...escrow, freelancerId: name };
    dispatch({ type: ACTIONS.SET_ESCROW, payload: updated });
  };

  return (
    <div className="scorer-panel">
      <div className="scorer-header">
        <h4>🎯 AI Agent Scorer</h4>
        <p className="text-muted">Domain: {projectDomain}</p>
      </div>

      <button
        className="btn btn-accent btn-sm"
        onClick={handleScore}
        disabled={loading || freelancers.length === 0}
      >
        {loading ? <><span className="spinner" /> Scoring...</> : '⚡ Score Freelancer Match'}
      </button>

      {state.errors.scorer && (
        <div className="error-msg">❌ {state.errors.scorer}</div>
      )}

      {assignScores.length > 0 && (
        <div className="scorer-results">
          {assignScores.map((s, i) => (
            <div key={i} className="scorer-card">
              <div className="scorer-rank">#{i + 1}</div>
              <div className="scorer-info">
                <h5>{s.name}</h5>
                <div className="scorer-tags">
                  {s.skills?.map((sk, j) => (
                    <span key={j} className="skill-tag">{sk}</span>
                  ))}
                </div>
                {s.reasoning && <p className="scorer-reasoning">{s.reasoning}</p>}
              </div>
              <div className="scorer-bars">
                <div className="scorer-metric">
                  <span>Domain Match</span>
                  <div className="scorer-bar">
                    <div className="scorer-bar-fill" style={{ width: `${s.domainMatch}%`, background: 'var(--cyan)' }} />
                  </div>
                  <span className="mono">{s.domainMatch}%</span>
                </div>
                <div className="scorer-metric">
                  <span>PFI</span>
                  <div className="scorer-bar">
                    <div className="scorer-bar-fill" style={{ width: `${s.pfiScore}%`, background: 'var(--green)' }} />
                  </div>
                  <span className="mono">{s.pfiScore}</span>
                </div>
                <div className="scorer-metric">
                  <span>Total</span>
                  <div className="scorer-bar">
                    <div className="scorer-bar-fill accent" style={{ width: `${s.totalScore}%` }} />
                  </div>
                  <span className="mono">{s.totalScore}</span>
                </div>
              </div>
              <button className="btn btn-sm btn-primary" onClick={() => handleAssign(s.freelancerId, s.name)}>
                Assign
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
