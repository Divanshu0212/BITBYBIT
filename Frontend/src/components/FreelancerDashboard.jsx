import React, { useState, useEffect } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';
import AQAReport from './AQAReport';

export default function FreelancerDashboard({ state, dispatch, mode = 'browse' }) {
  const [selectedMs, setSelectedMs] = useState(null);
  const [submissionText, setSubmissionText] = useState('');
  const [submissionUrl, setSubmissionUrl] = useState('');
  const [selectedProject, setSelectedProject] = useState(null);
  const [submissionLoading, setSubmissionLoading] = useState(false);
  const [submissionResult, setSubmissionResult] = useState(null);

  // Proposal form state
  const [showProposalForm, setShowProposalForm] = useState(null); // project id
  const [coverLetter, setCoverLetter] = useState('');
  const [bidAmount, setBidAmount] = useState('');
  const [estDays, setEstDays] = useState('');
  const [proposalLoading, setProposalLoading] = useState(false);
  const [proposalSuccess, setProposalSuccess] = useState(null);

  // Load data based on mode
  useEffect(() => {
    if (mode === 'browse') {
      loadOpenProjects();
    } else if (mode === 'proposals') {
      loadOwnProposals();
    } else if (mode === 'projects') {
      loadProjects();
    }
  }, [mode]);

  const loadOpenProjects = async () => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: { openProjects: true } });
    try {
      const projects = await api.listOpenProjects();
      dispatch({ type: ACTIONS.SET_OPEN_PROJECTS, payload: projects });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { openProjects: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { openProjects: false } });
    }
  };

  const loadOwnProposals = async () => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: { proposals: true } });
    try {
      const proposals = await api.listOwnProposals();
      dispatch({ type: ACTIONS.SET_OWN_PROPOSALS, payload: proposals });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { proposals: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { proposals: false } });
    }
  };

  const loadProjects = async () => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: { projects: true } });
    try {
      const projects = await api.listFreelancerProjects();
      dispatch({ type: ACTIONS.SET_PROJECTS, payload: projects });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { projects: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { projects: false } });
    }
  };

  const handleSubmitProposal = async (projectId) => {
    if (!coverLetter.trim() || coverLetter.length < 20) return;
    setProposalLoading(true);
    setProposalSuccess(null);
    try {
      await api.submitProposal(projectId, {
        coverLetter,
        bidAmount: bidAmount ? parseFloat(bidAmount) : undefined,
        estimatedDays: estDays ? parseInt(estDays) : undefined,
      });
      setProposalSuccess(projectId);
      setCoverLetter('');
      setBidAmount('');
      setEstDays('');
      setShowProposalForm(null);
      await loadOpenProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { proposal: err.message } });
    } finally {
      setProposalLoading(false);
    }
  };

  const handleWithdrawProposal = async (proposalId) => {
    try {
      await api.withdrawProposal(proposalId);
      await loadOwnProposals();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { proposal: err.message } });
    }
  };

  const handleActivate = async (project, milestone) => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: { activate: true } });
    try {
      await api.activateMilestone(project.id, milestone.id);
      const updated = await api.getFreelancerProject(project.id);
      setSelectedProject(updated);
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { freelancer: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { activate: false } });
    }
  };

  const handleSubmitWork = async (project, milestone) => {
    if (!submissionText.trim()) return;
    setSubmissionLoading(true);
    setSubmissionResult(null);
    dispatch({ type: ACTIONS.SET_ERROR, payload: { aqa: null } });

    try {
      const result = await api.submitWork(
        project.id, milestone.id,
        submissionText, submissionUrl || null
      );

      setSubmissionResult(result);
      dispatch({
        type: ACTIONS.SET_AQA_RESULT,
        payload: { milestoneId: milestone.id, result: result.aqa_result }
      });

      const updated = await api.getFreelancerProject(project.id);
      setSelectedProject(updated);
      await loadProjects();

      setSubmissionText('');
      setSubmissionUrl('');
      setSelectedMs(null);
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { aqa: err.message } });
    } finally {
      setSubmissionLoading(false);
    }
  };

  const statusIcon = (status) => ({
    PENDING: '⏳', IN_PROGRESS: '🔨', WORK_SUBMITTED: '📤',
    AQA_REVIEW: '🔍', PAID_FULL: '✅', PAID_PARTIAL: '⚠️', REFUND_INITIATED: '🔄',
  }[status] || '📌');

  const statusClass = (status) => {
    if (['PAID_FULL'].includes(status)) return 'status-success';
    if (['PAID_PARTIAL'].includes(status)) return 'status-warning';
    if (['REFUND_INITIATED'].includes(status)) return 'status-danger';
    if (['IN_PROGRESS', 'WORK_SUBMITTED', 'AQA_REVIEW'].includes(status)) return 'status-active';
    return 'status-pending';
  };

  const proposalStatusColor = (status) => ({
    pending: 'var(--yellow)',
    accepted: 'var(--green)',
    rejected: 'var(--red)',
    withdrawn: 'var(--muted)',
  }[status] || 'var(--muted)');

  const proposalStatusIcon = (status) => ({
    pending: '⏳',
    accepted: '✅',
    rejected: '❌',
    withdrawn: '↩️',
  }[status] || '📌');

  // ── BROWSE MODE: Find open projects ──────────────────────────────────
  if (mode === 'browse') {
    const openProjects = state.openProjects || [];

    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>🔍 Find Work</h2>
          <button className="btn btn-sm btn-ghost" onClick={loadOpenProjects}>
            🔄 Refresh
          </button>
        </div>

        {state.errors.openProjects && <div className="error-msg">❌ {state.errors.openProjects}</div>}
        {state.errors.proposal && <div className="error-msg">❌ {state.errors.proposal}</div>}

        {proposalSuccess && (
          <div className="success-banner animate-fade-in" style={{ marginBottom: 16 }}>
            <h3>🎯 Proposal Submitted!</h3>
            <p>Your proposal has been sent to the client. You'll be notified when they respond.</p>
          </div>
        )}

        {openProjects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <h3>No Open Projects</h3>
            <p>No projects are currently accepting proposals. Check back later!</p>
          </div>
        ) : (
          <div className="project-grid">
            {openProjects.map(p => (
              <div key={p.id} className="project-card browse-card">
                <div className="project-card-header">
                  <span className="project-status" style={{ color: 'var(--green)' }}>
                    💰 OPEN FOR PROPOSALS
                  </span>
                  {p.risk_level && (
                    <span className={`risk-badge risk-${(p.risk_level || 'medium').toLowerCase()}`}>
                      {p.risk_level}
                    </span>
                  )}
                </div>

                <p className="project-desc">
                  {p.description.length > 180 ? p.description.slice(0, 180) + '…' : p.description}
                </p>

                <div className="browse-meta">
                  <div className="browse-meta-row">
                    {p.budget && <span className="mono browse-budget">💰 ${p.budget.toLocaleString()}</span>}
                    {p.total_estimated_days && <span>📅 {p.total_estimated_days} days</span>}
                    <span>📦 {p.milestone_count} milestones</span>
                  </div>
                  <div className="browse-meta-row">
                    <span className="browse-client">🏢 {p.employer_name}</span>
                    <span className="browse-proposals">
                      📨 {p.proposal_count} proposal{p.proposal_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>

                {/* Mini milestone preview */}
                {p.milestones && p.milestones.length > 0 && (
                  <div className="browse-milestones">
                    {p.milestones.slice(0, 3).map((ms, i) => (
                      <span key={i} className="browse-ms-tag">
                        <span className="ms-index">M{i + 1}</span> {ms.title}
                      </span>
                    ))}
                    {p.milestones.length > 3 && (
                      <span className="browse-ms-more">+{p.milestones.length - 3} more</span>
                    )}
                  </div>
                )}

                {p.has_proposed ? (
                  <div className="browse-proposed-badge">
                    ✅ Proposal Sent
                  </div>
                ) : (
                  <button
                    className="btn btn-primary btn-block"
                    onClick={() => {
                      setShowProposalForm(p.id);
                      setCoverLetter('');
                      setBidAmount('');
                      setEstDays('');
                      setProposalSuccess(null);
                    }}
                  >
                    📝 Submit Proposal
                  </button>
                )}

                {/* Proposal Form (inline) */}
                {showProposalForm === p.id && (
                  <div className="proposal-form animate-slide-up">
                    <h5>Write Your Proposal</h5>
                    <textarea
                      className="input-textarea"
                      rows={5}
                      value={coverLetter}
                      onChange={e => setCoverLetter(e.target.value)}
                      placeholder="Introduce yourself, explain why you're the best fit for this project, and describe your approach (minimum 20 characters)..."
                    />
                    <div className="form-grid">
                      <div className="form-group">
                        <label className="input-label">Your Bid (USD)</label>
                        <input
                          type="number" className="input-field mono" value={bidAmount}
                          onChange={e => setBidAmount(e.target.value)}
                          placeholder={p.budget ? `Budget: $${p.budget.toLocaleString()}` : 'Optional'}
                          min="1"
                        />
                      </div>
                      <div className="form-group">
                        <label className="input-label">Est. Completion (days)</label>
                        <input
                          type="number" className="input-field" value={estDays}
                          onChange={e => setEstDays(e.target.value)}
                          placeholder={p.total_estimated_days ? `Est: ${p.total_estimated_days}d` : 'Optional'}
                          min="1"
                        />
                      </div>
                    </div>
                    <div className="btn-row">
                      <button className="btn btn-ghost" onClick={() => setShowProposalForm(null)}>Cancel</button>
                      <button
                        className="btn btn-primary"
                        onClick={() => handleSubmitProposal(p.id)}
                        disabled={coverLetter.length < 20 || proposalLoading}
                      >
                        {proposalLoading ? <><span className="spinner" /> Submitting...</> : '🚀 Send Proposal'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── PROPOSALS MODE: View own proposals ────────────────────────────────
  if (mode === 'proposals') {
    const proposals = state.ownProposals || [];

    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>📨 My Proposals</h2>
          <button className="btn btn-sm btn-ghost" onClick={loadOwnProposals}>
            🔄 Refresh
          </button>
        </div>

        {state.errors.proposals && <div className="error-msg">❌ {state.errors.proposals}</div>}

        {proposals.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📨</div>
            <h3>No Proposals Yet</h3>
            <p>Browse open projects and submit your first proposal to get started.</p>
            <button className="btn btn-primary" onClick={() => dispatch({ type: ACTIONS.SET_VIEW, payload: 'browse' })}>
              🔍 Find Work
            </button>
          </div>
        ) : (
          <div className="proposals-list">
            {proposals.map(prop => (
              <div key={prop.id} className={`proposal-card proposal-${prop.status}`}>
                <div className="proposal-card-header">
                  <div className="proposal-status-row">
                    <span className="proposal-status-badge" style={{
                      color: proposalStatusColor(prop.status),
                      borderColor: proposalStatusColor(prop.status),
                    }}>
                      {proposalStatusIcon(prop.status)} {prop.status.toUpperCase()}
                    </span>
                    <span className="proposal-date mono">
                      {new Date(prop.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <h4 className="proposal-project-title">
                    🏢 {prop.employer_name}
                  </h4>
                </div>

                <p className="proposal-project-desc">
                  {prop.project_description?.length > 160
                    ? prop.project_description.slice(0, 160) + '…'
                    : prop.project_description}
                </p>

                <div className="proposal-details">
                  {prop.project_budget && (
                    <span className="mono">💰 Project Budget: ${prop.project_budget.toLocaleString()}</span>
                  )}
                  {prop.bid_amount && (
                    <span className="mono" style={{ color: 'var(--cyan)' }}>🎯 Your Bid: ${prop.bid_amount.toLocaleString()}</span>
                  )}
                  {prop.estimated_days && (
                    <span>📅 {prop.estimated_days} days est.</span>
                  )}
                </div>

                <div className="proposal-cover-letter">
                  <strong>Your Proposal:</strong>
                  <p>{prop.cover_letter.length > 200 ? prop.cover_letter.slice(0, 200) + '…' : prop.cover_letter}</p>
                </div>

                {prop.status === 'pending' && (
                  <div className="proposal-actions">
                    <button
                      className="btn btn-sm btn-ghost"
                      onClick={() => handleWithdrawProposal(prop.id)}
                    >
                      ↩️ Withdraw Proposal
                    </button>
                  </div>
                )}

                {prop.status === 'accepted' && (
                  <div className="proposal-accepted-banner">
                    🎉 Your proposal was accepted! Check your Active Projects.
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── PROJECTS MODE: Active assigned projects ──────────────────────────
  // Project list view
  if (!selectedProject) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>👩‍💻 Active Projects</h2>
          <button className="btn btn-sm btn-ghost" onClick={loadProjects}>
            🔄 Refresh
          </button>
        </div>

        {state.errors.projects && <div className="error-msg">❌ {state.errors.projects}</div>}

        {state.projects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h3>No Active Projects</h3>
            <p>Submit proposals on open projects to get assigned work.</p>
            <button className="btn btn-primary" onClick={() => dispatch({ type: ACTIONS.SET_VIEW, payload: 'browse' })}>
              🔍 Find Work
            </button>
          </div>
        ) : (
          <div className="project-grid">
            {state.projects.map(p => (
              <div key={p.id} className="project-card" onClick={() => setSelectedProject(p)}>
                <div className="project-card-header">
                  <span className="project-status" style={{
                    color: p.status === 'active' ? 'var(--green)' : p.status === 'completed' ? 'var(--cyan)' : 'var(--yellow)'
                  }}>
                    {p.status === 'active' ? '🔨' : p.status === 'completed' ? '✅' : '💰'} {p.status.toUpperCase()}
                  </span>
                </div>
                <p className="project-desc">
                  {p.description.length > 120 ? p.description.slice(0, 120) + '…' : p.description}
                </p>
                <div className="project-card-footer">
                  {p.budget && <span className="mono">💰 ${p.budget.toLocaleString()}</span>}
                  <span>📦 {p.milestones?.length || 0} milestones</span>
                  {p.milestones && (
                    <span className="mono">
                      {p.milestones.filter(m => ['PAID_FULL', 'PAID_PARTIAL'].includes(m.status)).length}/{p.milestones.length} done
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Project detail view
  const milestones = selectedProject.milestones || [];

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <h2>👩‍💻 Project Work</h2>
        <button className="btn btn-ghost" onClick={() => { setSelectedProject(null); setSubmissionResult(null); }}>
          ← Back to Projects
        </button>
      </div>

      {state.errors.freelancer && <div className="error-msg">❌ {state.errors.freelancer}</div>}
      {state.errors.aqa && <div className="error-msg">❌ {state.errors.aqa}</div>}

      {/* Last submission result */}
      {submissionResult && (
        <div className={`success-banner animate-fade-in ${submissionResult.action_taken.includes('REFUND') ? 'banner-danger' : ''}`}>
          <h3>Submission Result: {submissionResult.action_taken}</h3>
          <p>Milestone status: {submissionResult.milestone_status}</p>
        </div>
      )}

      <div className="milestone-list">
        {milestones.map((ms, i) => (
          <div key={ms.id} className={`freelancer-ms-card ${statusClass(ms.status)}`}>
            <div className="fms-header">
              <span className="ms-index">M{i + 1}</span>
              <h4>{ms.title}</h4>
              {ms.task_type && <span className={`task-type-badge ${ms.task_type}`}>{ms.task_type}</span>}
              <span className={`status-badge ${statusClass(ms.status)}`}>
                {statusIcon(ms.status)} {ms.status.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="fms-body">
              <div className="fms-meta">
                <span className="domain-tag">{ms.domain}</span>
                <span className="mono">💵 ${ms.payment_amount?.toLocaleString()}</span>
                <span>⏱ {ms.estimated_days} days</span>
                {ms.payment_released > 0 && (
                  <span className="mono" style={{ color: 'var(--green)' }}>💸 ${ms.payment_released.toLocaleString()} released</span>
                )}
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

            <div className="fms-actions">
              {ms.status === 'PENDING' && (
                <button className="btn btn-accent"
                  onClick={() => handleActivate(selectedProject, ms)}
                  disabled={state.loading.activate}>
                  {state.loading.activate ? <><span className="spinner" /> Activating...</> : '▶ Activate Milestone'}
                </button>
              )}
              {ms.status === 'IN_PROGRESS' && (
                <button className="btn btn-primary" onClick={() => setSelectedMs(ms.id)}>
                  📝 Submit Work
                </button>
              )}
            </div>

            {/* Submission Form */}
            {selectedMs === ms.id && ms.status === 'IN_PROGRESS' && (
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
                    onClick={() => handleSubmitWork(selectedProject, ms)}
                    disabled={!submissionText.trim() || submissionLoading}
                  >
                    {submissionLoading ? <><span className="spinner" /> Running AQA Analysis...</> : '🚀 Submit for AQA Review'}
                  </button>
                </div>
              </div>
            )}

            {/* AQA Results */}
            {ms.aqa_result && (
              <AQAReport result={ms.aqa_result} milestoneIndex={i} milestone={ms} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
