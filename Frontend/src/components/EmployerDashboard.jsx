import React, { useState } from 'react';
import { ACTIONS } from '../store/actions';
import { decomposeProject, generateDemoProject } from '../geminiApi';
import { EscrowContract } from '../EscrowContract';

// Simple SVG-based DAG renderer
function DAGView({ milestones, dag }) {
  if (!milestones || milestones.length === 0) return null;

  const nodeW = 180, nodeH = 80, gapX = 60, gapY = 40;
  const cols = Math.min(milestones.length, 3);
  const rows = Math.ceil(milestones.length / cols);
  const svgW = cols * (nodeW + gapX) + gapX;
  const svgH = rows * (nodeH + gapY) + gapY;

  const positions = milestones.map((_, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    return {
      x: gapX + col * (nodeW + gapX),
      y: gapY + row * (nodeH + gapY),
      cx: gapX + col * (nodeW + gapX) + nodeW / 2,
      cy: gapY + row * (nodeH + gapY) + nodeH / 2,
    };
  });

  const complexityColor = (score) => {
    if (score <= 3) return 'var(--green)';
    if (score <= 6) return 'var(--yellow)';
    return 'var(--red)';
  };

  return (
    <div className="dag-container">
      <svg width={svgW} height={svgH} className="dag-svg">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--cyan)" />
          </marker>
        </defs>
        {/* Edges */}
        {dag && dag.map((edge, i) => {
          const from = positions[edge.from];
          const to = positions[edge.to];
          if (!from || !to) return null;
          return (
            <line key={`edge-${i}`}
              x1={from.cx} y1={from.cy + nodeH / 2}
              x2={to.cx} y2={to.cy - nodeH / 2}
              stroke="var(--cyan)" strokeWidth="2" opacity="0.5"
              markerEnd="url(#arrow)"
            />
          );
        })}
        {/* Nodes */}
        {milestones.map((ms, i) => {
          const p = positions[i];
          return (
            <g key={i}>
              <rect x={p.x} y={p.y} width={nodeW} height={nodeH} rx="8"
                fill="var(--surface)" stroke={complexityColor(ms.complexityScore)} strokeWidth="2"
              />
              <text x={p.cx} y={p.y + 20} textAnchor="middle" fill="var(--text)"
                fontSize="11" fontWeight="600">
                {ms.title?.length > 22 ? ms.title.slice(0, 20) + '…' : ms.title}
              </text>
              <text x={p.cx} y={p.y + 38} textAnchor="middle" fill="var(--muted)" fontSize="9">
                {ms.domain}
              </text>
              <text x={p.cx} y={p.y + 54} textAnchor="middle" fill="var(--cyan)" fontSize="10"
                fontFamily="'JetBrains Mono', monospace">
                {ms.estimatedDays}d • ⚡{ms.complexityScore}/10
              </text>
              <rect x={p.x + nodeW - 24} y={p.y + 4} width="20" height="16" rx="4"
                fill={complexityColor(ms.complexityScore)} opacity="0.2"
              />
              <text x={p.x + nodeW - 14} y={p.y + 15} textAnchor="middle"
                fill={complexityColor(ms.complexityScore)} fontSize="9" fontWeight="700">
                M{i + 1}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function EmployerDashboard({ state, dispatch }) {
  const [description, setDescription] = useState('');
  const [budget, setBudget] = useState('');
  const [deadline, setDeadline] = useState('');
  const [employerName, setEmployerName] = useState('');
  const [freelancerName, setFreelancerName] = useState('');
  const [phase, setPhase] = useState('input'); // 'input' | 'review' | 'confirmed'

  const isDecomposing = state.loading.decompose;
  const isDemoLoading = state.loading.demo;

  const handleDecompose = async () => {
    if (!description.trim() || !state.apiKey) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { decompose: true } });
    dispatch({ type: ACTIONS.SET_ERROR, payload: { decompose: null } });
    try {
      const result = await decomposeProject(description, state.apiKey);
      const milestones = result.milestones || [];
      const dag = result.dag || [];
      dispatch({ type: ACTIONS.SET_MILESTONES, payload: milestones });
      dispatch({ type: ACTIONS.SET_DAG, payload: dag });
      dispatch({ type: ACTIONS.SET_DECOMPOSITION, payload: result });
      setPhase('review');
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { decompose: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { decompose: false } });
    }
  };

  const handleGenerateDemo = async () => {
    if (!state.apiKey) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { demo: true } });
    try {
      const demo = await generateDemoProject(state.apiKey);
      setDescription(demo.projectDescription || '');
      setEmployerName(demo.employer?.name || '');
      setFreelancerName(demo.freelancer?.name || '');
      if (demo.freelancer) {
        dispatch({
          type: ACTIONS.SET_FREELANCERS,
          payload: [{
            id: 'f-' + Date.now(),
            name: demo.freelancer.name,
            skills: demo.freelancer.skills || [],
          }],
        });
      }
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { demo: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { demo: false } });
    }
  };

  const handleConfirm = () => {
    if (!budget || !employerName) return;
    const projectId = 'proj-' + Date.now();
    const contract = new EscrowContract({
      projectId,
      totalFunds: parseFloat(budget),
      milestones: state.milestones,
      employerId: employerName,
      freelancerId: freelancerName || 'Unassigned',
    });
    contract.depositFunds(parseFloat(budget));
    const escrowState = contract.getState();
    dispatch({ type: ACTIONS.SET_ESCROW, payload: escrowState });
    dispatch({ type: ACTIONS.APPEND_LEDGER, payload: escrowState.ledger });
    dispatch({
      type: ACTIONS.SET_PROJECT,
      payload: {
        project: {
          id: projectId,
          description,
          budget: parseFloat(budget),
          deadline,
          employer: employerName,
          freelancer: freelancerName,
          riskLevel: state.decomposition?.projectRiskLevel || 'Medium',
          totalEstimatedDays: state.decomposition?.totalEstimatedDays || 0,
        },
        replace: true,
      },
    });
    setPhase('confirmed');
  };

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>🏢 Employer Dashboard</h2>
        <p className="panel-subtitle">Describe your project and let AI decompose it into actionable milestones</p>
      </div>

      {phase === 'confirmed' && (
        <div className="success-banner animate-fade-in">
          <div className="success-icon">🎉</div>
          <h3>Project Funded &amp; Active</h3>
          <p>
            ${parseFloat(budget).toLocaleString()} locked in escrow across{' '}
            {state.milestones.length} milestones. Switch to the Freelancer tab to begin work.
          </p>
          <button className="btn btn-ghost" onClick={() => {
            dispatch({ type: ACTIONS.SET_VIEW, payload: 'freelancer' });
          }}>Go to Freelancer Dashboard →</button>
        </div>
      )}

      {phase !== 'confirmed' && (
        <>
          {/* Input Phase */}
          <div className="form-section">
            <div className="form-row">
              <label className="input-label">Project Description</label>
              <button
                className="btn btn-sm btn-accent"
                onClick={handleGenerateDemo}
                disabled={isDemoLoading || !state.apiKey}
              >
                {isDemoLoading ? '⏳ Generating...' : '🎲 Generate Demo Project'}
              </button>
            </div>
            <textarea
              className="input-textarea"
              rows={5}
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Describe your project in 2-4 sentences. Be as vague or specific as you like — the AI will decompose it into structured milestones..."
              disabled={phase === 'review'}
            />

            {state.errors.decompose && (
              <div className="error-msg">❌ {state.errors.decompose}</div>
            )}
            {state.errors.demo && (
              <div className="error-msg">❌ {state.errors.demo}</div>
            )}

            {phase === 'input' && (
              <button
                className="btn btn-primary btn-lg"
                onClick={handleDecompose}
                disabled={isDecomposing || !description.trim() || !state.apiKey}
              >
                {isDecomposing ? (
                  <><span className="spinner" /> Decomposing Requirements...</>
                ) : (
                  '🤖 Decompose with AI'
                )}
              </button>
            )}
          </div>

          {/* Review Phase */}
          {phase === 'review' && state.milestones.length > 0 && (
            <div className="animate-fade-in">
              <div className="decomp-meta">
                <span className={`risk-badge risk-${(state.decomposition?.projectRiskLevel || 'medium').toLowerCase()}`}>
                  ⚠ {state.decomposition?.projectRiskLevel || 'Medium'} Risk
                </span>
                <span className="meta-tag">
                  📅 {state.decomposition?.totalEstimatedDays || '?'} days estimated
                </span>
                <span className="meta-tag">
                  📦 {state.milestones.length} milestones
                </span>
              </div>

              <DAGView milestones={state.milestones} dag={state.dag} />

              {/* Milestone Cards */}
              <div className="milestone-cards">
                {state.milestones.map((ms, i) => (
                  <div key={i} className="milestone-card">
                    <div className="ms-card-header">
                      <span className="ms-index">M{i + 1}</span>
                      <h4>{ms.title}</h4>
                      <span className="domain-tag">{ms.domain}</span>
                    </div>
                    <p className="ms-desc">{ms.description}</p>
                    <div className="ms-meta">
                      <span>⏱ {ms.estimatedDays} days</span>
                      <span>⚡ Complexity: {ms.complexityScore}/10</span>
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
                ))}
              </div>

              {/* Confirm Form */}
              <div className="confirm-section">
                <h3>Finalize Project</h3>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="input-label">Employer Name *</label>
                    <input
                      type="text" className="input-field" value={employerName}
                      onChange={e => setEmployerName(e.target.value)} placeholder="John Doe"
                    />
                  </div>
                  <div className="form-group">
                    <label className="input-label">Freelancer Name</label>
                    <input
                      type="text" className="input-field" value={freelancerName}
                      onChange={e => setFreelancerName(e.target.value)} placeholder="Jane Smith"
                    />
                  </div>
                  <div className="form-group">
                    <label className="input-label">Total Budget (USD) *</label>
                    <input
                      type="number" className="input-field mono" value={budget}
                      onChange={e => setBudget(e.target.value)} placeholder="5000" min="1"
                    />
                  </div>
                  <div className="form-group">
                    <label className="input-label">Deadline</label>
                    <input
                      type="date" className="input-field" value={deadline}
                      onChange={e => setDeadline(e.target.value)}
                    />
                  </div>
                </div>
                <div className="btn-row">
                  <button className="btn btn-ghost" onClick={() => {
                    setPhase('input');
                    dispatch({ type: ACTIONS.SET_MILESTONES, payload: [] });
                    dispatch({ type: ACTIONS.SET_DAG, payload: [] });
                  }}>
                    ← Re-decompose
                  </button>
                  <button
                    className="btn btn-primary btn-lg"
                    onClick={handleConfirm}
                    disabled={!budget || !employerName}
                  >
                    🔒 Lock Funds &amp; Create Contract
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
