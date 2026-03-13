import React, { useState, useEffect } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';

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
        {milestones.map((ms, i) => {
          const p = positions[i];
          return (
            <g key={i}>
              <rect x={p.x} y={p.y} width={nodeW} height={nodeH} rx="8"
                fill="var(--surface)" stroke={complexityColor(ms.complexity_score || ms.complexityScore)} strokeWidth="2"
              />
              <text x={p.cx} y={p.y + 20} textAnchor="middle" fill="var(--text)"
                fontSize="11" fontWeight="600">
                {(ms.title || '').length > 22 ? ms.title.slice(0, 20) + '…' : ms.title}
              </text>
              <text x={p.cx} y={p.y + 38} textAnchor="middle" fill="var(--muted)" fontSize="9">
                {ms.domain}
              </text>
              <text x={p.cx} y={p.y + 54} textAnchor="middle" fill="var(--cyan)" fontSize="10"
                fontFamily="'JetBrains Mono', monospace">
                {ms.estimated_days || ms.estimatedDays}d • ⚡{ms.complexity_score || ms.complexityScore}/10
              </text>
              <rect x={p.x + nodeW - 24} y={p.y + 4} width="20" height="16" rx="4"
                fill={complexityColor(ms.complexity_score || ms.complexityScore)} opacity="0.2"
              />
              <text x={p.x + nodeW - 14} y={p.y + 15} textAnchor="middle"
                fill={complexityColor(ms.complexity_score || ms.complexityScore)} fontSize="9" fontWeight="700">
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
  const [phase, setPhase] = useState('list'); // 'list' | 'create' | 'review' | 'fund' | 'assign'
  const [selectedProject, setSelectedProject] = useState(null);
  const [freelancerList, setFreelancerList] = useState([]);
  const [decomposition, setDecomposition] = useState(null);

  const isLoading = state.loading;

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: { projects: true } });
    try {
      const projects = await api.listEmployerProjects();
      dispatch({ type: ACTIONS.SET_PROJECTS, payload: projects });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { projects: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { projects: false } });
    }
  };

  const handleCreate = async () => {
    if (!description.trim()) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { create: true } });
    dispatch({ type: ACTIONS.SET_ERROR, payload: { create: null } });
    try {
      const project = await api.createProject({
        description,
        budget: budget ? parseFloat(budget) : undefined,
        deadline: deadline || undefined,
      });
      setSelectedProject(project);
      setPhase('review');
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { create: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { create: false } });
    }
  };

  const handleDecompose = async () => {
    if (!selectedProject) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { decompose: true } });
    dispatch({ type: ACTIONS.SET_ERROR, payload: { decompose: null } });
    try {
      const project = await api.decomposeProject(selectedProject.id, description || selectedProject.description);
      setSelectedProject(project);
      setDecomposition(project.decomposition);
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { decompose: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { decompose: false } });
    }
  };

  const handleFund = async () => {
    if (!selectedProject || !budget) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { fund: true } });
    dispatch({ type: ACTIONS.SET_ERROR, payload: { fund: null } });
    try {
      const project = await api.fundProject(selectedProject.id, parseFloat(budget));
      setSelectedProject(project);
      setPhase('assign');
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { fund: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { fund: false } });
    }
  };

  const handleLoadFreelancers = async () => {
    try {
      const list = await api.listFreelancers();
      setFreelancerList(list);
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { freelancers: err.message } });
    }
  };

  const handleAssign = async (freelancerId) => {
    if (!selectedProject) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { assign: true } });
    try {
      const project = await api.assignFreelancer(selectedProject.id, freelancerId);
      setSelectedProject(project);
      setPhase('list');
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { assign: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { assign: false } });
    }
  };

  const openProject = async (project) => {
    setSelectedProject(project);
    setDecomposition(project.decomposition);
    if (project.status === 'draft') {
      setDescription(project.description);
      setPhase('review');
    } else if (project.status === 'decomposed') {
      setBudget(project.budget ? String(project.budget) : '');
      setPhase('review');
    } else if (project.status === 'funded') {
      setPhase('assign');
      await handleLoadFreelancers();
    } else {
      setPhase('detail');
    }
  };

  const statusIcon = {
    draft: '📝', decomposed: '🤖', funded: '💰', active: '🔨', completed: '✅',
  };

  const statusColor = {
    draft: 'var(--muted)', decomposed: 'var(--cyan)', funded: 'var(--yellow)',
    active: 'var(--green)', completed: 'var(--green)',
  };

  // Project List View
  if (phase === 'list') {
    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>🏢 Employer Dashboard</h2>
          <button className="btn btn-primary" onClick={() => {
            setPhase('create');
            setDescription('');
            setBudget('');
            setDeadline('');
            setSelectedProject(null);
            setDecomposition(null);
          }}>
            + New Project
          </button>
        </div>

        {state.errors.projects && (
          <div className="error-msg">❌ {state.errors.projects}</div>
        )}

        {state.projects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h3>No Projects Yet</h3>
            <p>Create your first project and let AI decompose it into actionable milestones.</p>
          </div>
        ) : (
          <div className="project-grid">
            {state.projects.map(p => (
              <div key={p.id} className="project-card" onClick={() => openProject(p)}>
                <div className="project-card-header">
                  <span className="project-status" style={{ color: statusColor[p.status] }}>
                    {statusIcon[p.status]} {p.status.toUpperCase()}
                  </span>
                  {p.risk_level && (
                    <span className={`risk-badge risk-${(p.risk_level || 'medium').toLowerCase()}`}>
                      {p.risk_level}
                    </span>
                  )}
                </div>
                <p className="project-desc">{p.description.length > 120 ? p.description.slice(0, 120) + '…' : p.description}</p>
                <div className="project-card-footer">
                  {p.budget && <span className="mono">💰 ${p.budget.toLocaleString()}</span>}
                  {p.total_estimated_days && <span>📅 {p.total_estimated_days}d</span>}
                  <span>📦 {p.milestones?.length || 0} milestones</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Create / Review / Fund / Assign Views
  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>🏢 {phase === 'create' ? 'New Project' : phase === 'assign' ? 'Assign Freelancer' : 'Project Details'}</h2>
        <button className="btn btn-ghost" onClick={() => { setPhase('list'); setSelectedProject(null); }}>
          ← Back to Projects
        </button>
      </div>

      {/* Create / Decompose Phase */}
      {(phase === 'create' || phase === 'review') && (
        <>
          <div className="form-section">
            <div className="form-group">
              <label className="input-label">Project Description</label>
              <textarea
                className="input-textarea"
                rows={5}
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Describe your project in 2-4 sentences..."
                disabled={selectedProject && selectedProject.status !== 'draft'}
              />
            </div>

            {state.errors.create && <div className="error-msg">❌ {state.errors.create}</div>}
            {state.errors.decompose && <div className="error-msg">❌ {state.errors.decompose}</div>}

            {!selectedProject && (
              <button
                className="btn btn-primary btn-lg"
                onClick={handleCreate}
                disabled={isLoading.create || !description.trim()}
              >
                {isLoading.create ? <><span className="spinner" /> Creating...</> : '📝 Create Project'}
              </button>
            )}

            {selectedProject && selectedProject.milestones?.length === 0 && (
              <button
                className="btn btn-primary btn-lg"
                onClick={handleDecompose}
                disabled={isLoading.decompose}
              >
                {isLoading.decompose ? <><span className="spinner" /> Decomposing...</> : '🤖 Decompose with AI'}
              </button>
            )}
          </div>

          {/* Milestones Review */}
          {selectedProject && selectedProject.milestones?.length > 0 && (
            <div className="animate-fade-in">
              <div className="decomp-meta">
                <span className={`risk-badge risk-${(selectedProject.risk_level || 'medium').toLowerCase()}`}>
                  ⚠ {selectedProject.risk_level || 'Medium'} Risk
                </span>
                <span className="meta-tag">📅 {selectedProject.total_estimated_days || '?'} days estimated</span>
                <span className="meta-tag">📦 {selectedProject.milestones.length} milestones</span>
              </div>

              <DAGView
                milestones={selectedProject.milestones}
                dag={decomposition?.dag || []}
              />

              <div className="milestone-cards">
                {selectedProject.milestones.map((ms, i) => (
                  <div key={ms.id} className="milestone-card">
                    <div className="ms-card-header">
                      <span className="ms-index">M{i + 1}</span>
                      <h4>{ms.title}</h4>
                      <span className="domain-tag">{ms.domain}</span>
                    </div>
                    <p className="ms-desc">{ms.description}</p>
                    <div className="ms-meta">
                      <span>⏱ {ms.estimated_days} days</span>
                      <span>⚡ Complexity: {ms.complexity_score}/10</span>
                      {ms.payment_amount > 0 && <span className="mono">💵 ${ms.payment_amount.toLocaleString()}</span>}
                    </div>
                    <div className="criteria-list">
                      <strong>Acceptance Criteria:</strong>
                      <ul>
                        {(ms.acceptance_criteria || []).map((c, j) => (
                          <li key={j}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>

              {/* Fund Section */}
              {selectedProject.status === 'decomposed' && (
                <div className="confirm-section">
                  <h3>💰 Fund Project</h3>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="input-label">Total Budget (USD) *</label>
                      <input
                        type="number" className="input-field mono" value={budget}
                        onChange={e => setBudget(e.target.value)} placeholder="5000" min="1"
                      />
                    </div>
                  </div>
                  {state.errors.fund && <div className="error-msg">❌ {state.errors.fund}</div>}
                  <div className="btn-row">
                    <button className="btn btn-ghost" onClick={() => { handleDecompose(); }}>
                      ← Re-decompose
                    </button>
                    <button
                      className="btn btn-primary btn-lg"
                      onClick={handleFund}
                      disabled={!budget || isLoading.fund}
                    >
                      {isLoading.fund ? <><span className="spinner" /> Funding...</> : '🔒 Lock Funds in Escrow'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Assign Freelancer Phase */}
      {phase === 'assign' && selectedProject && (
        <div className="animate-fade-in">
          <div className="success-banner">
            <div className="success-icon">💰</div>
            <h3>Project Funded — ${selectedProject.budget?.toLocaleString()}</h3>
            <p>Select a freelancer to assign to this project.</p>
          </div>

          {freelancerList.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">👥</div>
              <h3>No Freelancers Available</h3>
              <p>Register freelancer accounts to see them here.</p>
              <button className="btn btn-accent" onClick={handleLoadFreelancers}>
                🔄 Refresh List
              </button>
            </div>
          ) : (
            <div className="freelancer-list">
              <h3>Available Freelancers</h3>
              {freelancerList.map(fl => (
                <div key={fl.id} className="freelancer-card">
                  <div className="fl-info">
                    <h4>{fl.name}</h4>
                    <p className="fl-email">{fl.email}</p>
                    <div className="fl-skills">
                      {(fl.skills || []).map((s, i) => (
                        <span key={i} className="skill-tag">{s}</span>
                      ))}
                    </div>
                    {fl.pfi_score !== undefined && (
                      <span className="pfi-mini-badge">PFI: {fl.pfi_score}</span>
                    )}
                  </div>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => handleAssign(fl.id)}
                    disabled={isLoading.assign}
                  >
                    {isLoading.assign ? 'Assigning...' : 'Assign →'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Detail View */}
      {phase === 'detail' && selectedProject && (
        <div className="animate-fade-in">
          <div className="project-detail-header">
            <span className="project-status" style={{ color: statusColor[selectedProject.status] }}>
              {statusIcon[selectedProject.status]} {selectedProject.status.toUpperCase()}
            </span>
            {selectedProject.budget && <span className="mono">💰 ${selectedProject.budget.toLocaleString()}</span>}
          </div>
          <p className="project-desc">{selectedProject.description}</p>

          <div className="milestone-cards">
            {(selectedProject.milestones || []).map((ms, i) => (
              <div key={ms.id} className={`milestone-card ${ms.status === 'PAID_FULL' ? 'status-success' : ms.status === 'REFUND_INITIATED' ? 'status-danger' : ''}`}>
                <div className="ms-card-header">
                  <span className="ms-index">M{i + 1}</span>
                  <h4>{ms.title}</h4>
                  <span className={`status-badge status-${ms.status === 'PAID_FULL' ? 'success' : ms.status === 'REFUND_INITIATED' ? 'danger' : 'active'}`}>
                    {ms.status.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="ms-meta">
                  <span className="mono">💵 ${ms.payment_amount?.toLocaleString()} allocated</span>
                  <span className="mono">💸 ${ms.payment_released?.toLocaleString()} released</span>
                </div>
                {ms.aqa_result && (
                  <div className="ms-aqa-mini">
                    <span>AQA Score: <strong style={{ color: ms.aqa_result.overallScore >= 60 ? 'var(--green)' : 'var(--red)' }}>
                      {ms.aqa_result.overallScore}/100
                    </strong></span>
                    <span> — {ms.aqa_result.paymentRecommendation?.replace(/_/g, ' ')}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
