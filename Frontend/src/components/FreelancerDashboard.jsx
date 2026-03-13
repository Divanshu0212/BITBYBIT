import React, { useState, useEffect } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';
import AQAReport from './AQAReport';

export default function FreelancerDashboard({ state, dispatch }) {
  const [selectedMs, setSelectedMs] = useState(null);
  const [submissionText, setSubmissionText] = useState('');
  const [submissionUrl, setSubmissionUrl] = useState('');
  const [selectedProject, setSelectedProject] = useState(null);
  const [submissionLoading, setSubmissionLoading] = useState(false);
  const [submissionResult, setSubmissionResult] = useState(null);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

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

  const handleActivate = async (project, milestone) => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: { activate: true } });
    try {
      await api.activateMilestone(project.id, milestone.id);
      // Refresh project
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

      // Refresh project
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

  // Project list view
  if (!selectedProject) {
    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>👩‍💻 Freelancer Dashboard</h2>
        </div>

        {state.errors.projects && <div className="error-msg">❌ {state.errors.projects}</div>}

        {state.projects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h3>No Assigned Projects</h3>
            <p>An employer needs to create a project and assign you to it.</p>
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
