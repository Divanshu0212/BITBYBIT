import React, { useState, useEffect } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';
import AQAReport from './AQAReport';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Building2, Wallet, ClipboardList, PenTool, CheckCircle2,
  DollarSign, Clock, AlertTriangle, AlertCircle, XCircle,
  Search, Package, Mail, Briefcase, RefreshCw, Send, Undo2, Play, SearchCode,
  Github, GitCommitHorizontal, Image, FileText, Plus, Trash2
} from 'lucide-react';

const CODE_KEYS = new Set(['correctness', 'security', 'test_coverage', 'maintainability']);
const DESIGN_KEYS = new Set(['visual_consistency', 'accessibility', 'responsive_completeness', 'export_readiness', 'requirements_coverage']);
const CONTENT_KEYS = new Set(['factuality', 'originality', 'readability', 'seo_structure', 'style_alignment']);

function detectModalities(milestone) {
  const tt = (milestone.task_type || 'mixed').toLowerCase();
  if (tt === 'code') return { code: true, design: false, content: false };
  if (tt === 'design') return { code: false, design: true, content: false };
  if (tt === 'content') return { code: false, design: false, content: true };

  const weights = milestone.scoring_weights;
  if (weights && typeof weights === 'object') {
    const keys = new Set(Object.keys(weights));
    const hasCode = [...keys].some(k => CODE_KEYS.has(k));
    const hasDesign = [...keys].some(k => DESIGN_KEYS.has(k));
    const hasContent = [...keys].some(k => CONTENT_KEYS.has(k));
    if (hasCode || hasDesign || hasContent) return { code: hasCode, design: hasDesign, content: hasContent };
  }
  return { code: true, design: true, content: false };
}

export default function FreelancerDashboard({ state, dispatch, mode = 'browse' }) {
  const [selectedMs, setSelectedMs] = useState(null);
  const [submissionText, setSubmissionText] = useState('');
  const [submissionUrl, setSubmissionUrl] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [commitHash, setCommitHash] = useState('');
  const [designUrls, setDesignUrls] = useState(['']);
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

    const filteredDesignUrls = designUrls.filter(u => u.trim());

    try {
      const result = await api.submitWork(
        project.id, milestone.id,
        submissionText, submissionUrl || null,
        repoUrl || null, commitHash || null,
        filteredDesignUrls.length > 0 ? filteredDesignUrls : null
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
      setRepoUrl('');
      setCommitHash('');
      setDesignUrls(['']);
      setSelectedMs(null);
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { aqa: err.message } });
    } finally {
      setSubmissionLoading(false);
    }
  };

  const statusIcon = (status) => ({
    PENDING: <Clock size={16} />, 
    IN_PROGRESS: <PenTool size={16} />, 
    WORK_SUBMITTED: <Send size={16} />,
    AQA_REVIEW: <SearchCode size={16} />, 
    PAID_FULL: <CheckCircle2 size={16} />, 
    PAID_PARTIAL: <AlertTriangle size={16} />, 
    REFUND_INITIATED: <Undo2 size={16} />,
  }[status] || <ClipboardList size={16} />);

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
    pending: <Clock size={16} />,
    accepted: <CheckCircle2 size={16} />,
    rejected: <XCircle size={16} />,
    withdrawn: <Undo2 size={16} />,
  }[status] || <ClipboardList size={16} />);

  // ── BROWSE MODE: Find open projects ──────────────────────────────────
  if (mode === 'browse') {
    const openProjects = state.openProjects || [];

    return (
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="dashboard-panel">
        <div className="panel-header">
          <h2 className="flex items-center gap-2"><Search size={24} color="var(--cyan)" /> Find Work</h2>
          <button className="btn btn-sm btn-ghost flex items-center gap-1" onClick={loadOpenProjects}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {state.errors.openProjects && <div className="error-msg flex items-center gap-1"><AlertCircle size={16} /> {state.errors.openProjects}</div>}
        {state.errors.proposal && <div className="error-msg flex items-center gap-1"><AlertCircle size={16} /> {state.errors.proposal}</div>}

        {proposalSuccess && (
          <div className="success-banner animate-fade-in" style={{ marginBottom: 16 }}>
            <h3>🎯 Proposal Submitted!</h3>
            <p>Your proposal has been sent to the client. You'll be notified when they respond.</p>
          </div>
        )}

        {openProjects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon text-gray-500 mb-4 flex justify-center"><Search size={48} /></div>
            <h3>No Open Projects</h3>
            <p>No projects are currently accepting proposals. Check back later!</p>
          </div>
        ) : (
          <div className="project-grid">
            {openProjects.map(p => (
              <motion.div whileHover={{ y: -5 }} key={p.id} className="project-card browse-card">
                <div className="project-card-header">
                  <span className="project-status flex items-center gap-1" style={{ color: 'var(--green)' }}>
                    <DollarSign size={14} /> OPEN FOR PROPOSALS
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
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    );
  }

  // ── PROPOSALS MODE: View own proposals ────────────────────────────────
  if (mode === 'proposals') {
    const proposals = state.ownProposals || [];

    return (
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="dashboard-panel">
        <div className="panel-header">
          <h2 className="flex items-center gap-2"><Mail size={24} color="var(--cyan)" /> My Proposals</h2>
          <button className="btn btn-sm btn-ghost flex items-center gap-1" onClick={loadOwnProposals}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {state.errors.proposals && <div className="error-msg">❌ {state.errors.proposals}</div>}

        {proposals.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon text-gray-500 mb-4 flex justify-center"><Mail size={48} /></div>
            <h3>No Proposals Yet</h3>
            <p>Browse open projects and submit your first proposal to get started.</p>
            <button className="btn btn-primary flex items-center gap-2" onClick={() => dispatch({ type: ACTIONS.SET_VIEW, payload: 'browse' })}>
              <Search size={18} /> Find Work
            </button>
          </div>
        ) : (
          <div className="proposals-list">
            {proposals.map(prop => (
              <motion.div whileHover={{ scale: 1.01 }} key={prop.id} className={`proposal-card proposal-${prop.status}`}>
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
                      className="btn btn-sm btn-ghost flex items-center gap-1"
                      onClick={() => handleWithdrawProposal(prop.id)}
                    >
                      <Undo2 size={14} /> Withdraw Proposal
                    </button>
                  </div>
                )}

                {prop.status === 'accepted' && (
                  <div className="proposal-accepted-banner">
                    🎉 Your proposal was accepted! Check your Active Projects.
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    );
  }

  // ── PROJECTS MODE: Active assigned projects ──────────────────────────
  // Project list view
  if (!selectedProject) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="dashboard-panel">
        <div className="panel-header">
          <h2 className="flex items-center gap-2"><Briefcase size={24} color="var(--cyan)" /> Active Projects</h2>
          <button className="btn btn-sm btn-ghost flex items-center gap-1" onClick={loadProjects}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {state.errors.projects && <div className="error-msg flex items-center gap-1"><AlertCircle size={16} /> {state.errors.projects}</div>}

        {state.projects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon text-gray-500 mb-4 flex justify-center"><Briefcase size={48} /></div>
            <h3>No Active Projects</h3>
            <p>Submit proposals on open projects to get assigned work.</p>
            <button className="btn btn-primary flex items-center gap-2" onClick={() => dispatch({ type: ACTIONS.SET_VIEW, payload: 'browse' })}>
              <Search size={18} /> Find Work
            </button>
          </div>
        ) : (
          <div className="project-grid">
            {state.projects.map(p => (
              <motion.div whileHover={{ y: -5 }} key={p.id} className="project-card" onClick={() => setSelectedProject(p)}>
                <div className="project-card-header">
                  <span className="project-status flex items-center gap-1" style={{
                    color: p.status === 'active' ? 'var(--green)' : p.status === 'completed' ? 'var(--cyan)' : 'var(--yellow)'
                  }}>
                    {p.status === 'active' ? <PenTool size={16} /> : p.status === 'completed' ? <CheckCircle2 size={16} /> : <DollarSign size={16} />} 
                    {p.status.toUpperCase()}
                  </span>
                </div>
                <p className="project-desc">
                  {p.description.length > 120 ? p.description.slice(0, 120) + '…' : p.description}
                </p>
                <div className="project-card-footer flex items-center gap-3">
                  {p.budget && <span className="mono flex items-center gap-1"><DollarSign size={14} /> {p.budget.toLocaleString()}</span>}
                  <span className="flex items-center gap-1"><Package size={14} /> {p.milestones?.length || 0} milestones</span>
                  {p.milestones && (
                    <span className="mono flex items-center gap-1 text-green-400">
                      <CheckCircle2 size={14} />
                      {p.milestones.filter(m => ['PAID_FULL', 'PAID_PARTIAL'].includes(m.status)).length}/{p.milestones.length} done
                    </span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    );
  }

  // Project detail view
  const milestones = selectedProject.milestones || [];

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="dashboard-panel">
      <div className="panel-header">
        <h2 className="flex items-center gap-2"><PenTool size={24} color="var(--cyan)" /> Project Work</h2>
        <button className="btn btn-ghost flex items-center gap-1" onClick={() => { setSelectedProject(null); setSubmissionResult(null); }}>
          <Undo2 size={16} /> Back to Projects
        </button>
      </div>

      {state.errors.freelancer && <div className="error-msg flex items-center gap-1"><AlertCircle size={16} /> {state.errors.freelancer}</div>}
      {state.errors.aqa && <div className="error-msg flex items-center gap-1"><AlertCircle size={16} /> {state.errors.aqa}</div>}

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
                <button className="btn btn-accent flex items-center gap-2"
                  onClick={() => handleActivate(selectedProject, ms)}
                  disabled={state.loading.activate}>
                  {state.loading.activate ? <><span className="spinner" /> Activating...</> : <><Play size={16} /> Activate Milestone</>}
                </button>
              )}
              {['IN_PROGRESS', 'PAID_PARTIAL', 'REFUND_INITIATED'].includes(ms.status) && (
                <button className="btn btn-primary flex items-center gap-2" onClick={() => setSelectedMs(ms.id)}>
                  <ClipboardList size={16} /> {ms.status === 'IN_PROGRESS' ? 'Submit Work' : 'Resubmit Work'}
                </button>
              )}
            </div>

            {/* Submission Form — modality-aware */}
            {selectedMs === ms.id && ['IN_PROGRESS', 'PAID_PARTIAL', 'REFUND_INITIATED'].includes(ms.status) && (() => {
              const mods = detectModalities(ms);
              const modLabels = [mods.code && 'Code', mods.design && 'Design', mods.content && 'Content'].filter(Boolean);
              const canSubmit = submissionText.trim()
                && (!mods.code || repoUrl.trim())
                && (!mods.design || designUrls.some(u => u.trim()));

              return (
                <div className="submission-form animate-fade-in">
                  <h5>{ms.status === 'IN_PROGRESS' ? 'Submit Work for Review' : 'Resubmit Work for Review'}</h5>

                  {modLabels.length > 1 && (
                    <div style={{
                      display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap',
                    }}>
                      {modLabels.map(label => (
                        <span key={label} className={`task-type-badge ${label.toLowerCase()}`} style={{ fontSize: 11 }}>
                          {label}
                        </span>
                      ))}
                      <span style={{ fontSize: 12, color: 'var(--muted)', alignSelf: 'center' }}>
                        — provide deliverables for each modality
                      </span>
                    </div>
                  )}

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

                  {/* Code fields */}
                  {mods.code && (
                    <div className="code-repo-fields" style={{ background: 'rgba(var(--cyan-rgb, 0,188,212), 0.04)', borderRadius: 8, padding: 14, marginTop: 8, border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--cyan)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Github size={14} /> Code Deliverables
                      </div>
                      <div className="repo-field-group">
                        <label className="input-label flex items-center gap-1">
                          GitHub Repository URL <span className="required-star">*</span>
                        </label>
                        <input
                          type="url"
                          className="input-field repo-url-field"
                          value={repoUrl}
                          onChange={e => setRepoUrl(e.target.value)}
                          placeholder="https://github.com/username/repo"
                          required
                        />
                        {!repoUrl.trim() && (
                          <span className="field-hint field-hint-warning">Required for code work</span>
                        )}
                      </div>
                      <div className="repo-field-group" style={{ marginTop: 8 }}>
                        <label className="input-label flex items-center gap-1">
                          <GitCommitHorizontal size={16} /> Commit Hash
                          <span className="optional-tag">optional</span>
                        </label>
                        <input
                          type="text"
                          className="input-field commit-hash-field mono"
                          value={commitHash}
                          onChange={e => setCommitHash(e.target.value)}
                          placeholder="e.g. a1b2c3d (pins verification to exact commit)"
                          maxLength={64}
                        />
                      </div>
                    </div>
                  )}

                  {/* Design fields */}
                  {mods.design && (
                    <div style={{ background: 'rgba(168,85,247,0.04)', borderRadius: 8, padding: 14, marginTop: 8, border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#a855f7', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Image size={14} /> Design Deliverables <span className="required-star">*</span>
                      </div>
                      {designUrls.map((url, idx) => (
                        <div key={idx} style={{ display: 'flex', gap: 8, marginBottom: 6, alignItems: 'center' }}>
                          <input
                            type="url"
                            className="input-field"
                            style={{ flex: 1 }}
                            value={url}
                            onChange={e => {
                              const next = [...designUrls];
                              next[idx] = e.target.value;
                              setDesignUrls(next);
                            }}
                            placeholder={idx === 0 ? 'Figma link, screenshot URL, or design file link' : 'Another design URL...'}
                          />
                          {designUrls.length > 1 && (
                            <button
                              className="btn btn-ghost"
                              style={{ padding: '4px 6px', minWidth: 0 }}
                              onClick={() => setDesignUrls(prev => prev.filter((_, i) => i !== idx))}
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      ))}
                      <button
                        className="btn btn-ghost flex items-center gap-1"
                        style={{ fontSize: 12, padding: '4px 10px' }}
                        onClick={() => setDesignUrls(prev => [...prev, ''])}
                      >
                        <Plus size={14} /> Add another URL
                      </button>
                      {!designUrls.some(u => u.trim()) && (
                        <span className="field-hint field-hint-warning" style={{ display: 'block', marginTop: 6 }}>
                          At least one design URL is required
                        </span>
                      )}
                    </div>
                  )}

                  {/* Content fields */}
                  {mods.content && (
                    <div style={{ background: 'rgba(34,197,94,0.04)', borderRadius: 8, padding: 14, marginTop: 8, border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--green)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <FileText size={14} /> Content Deliverables
                      </div>
                      <input
                        type="url"
                        className="input-field"
                        value={submissionUrl}
                        onChange={e => setSubmissionUrl(e.target.value)}
                        placeholder="Google Doc, Notion page, or content URL"
                      />
                    </div>
                  )}

                  {/* Non-code, non-design, non-content — fallback repo field */}
                  {!mods.code && !mods.design && !mods.content && (
                    <div className="repo-field-group">
                      <label className="input-label flex items-center gap-1">
                        <Github size={16} /> GitHub Repository URL
                        <span className="optional-tag">optional</span>
                      </label>
                      <input
                        type="url"
                        className="input-field"
                        value={repoUrl}
                        onChange={e => setRepoUrl(e.target.value)}
                        placeholder="https://github.com/username/repo (optional)"
                      />
                    </div>
                  )}

                  <div className="btn-row">
                    <button className="btn btn-ghost" onClick={() => { setSelectedMs(null); setDesignUrls(['']); }}>Cancel</button>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleSubmitWork(selectedProject, ms)}
                      disabled={!canSubmit || submissionLoading}
                    >
                      {submissionLoading
                        ? <><span className="spinner" /> Running AQA Analysis...</>
                        : modLabels.length > 1
                          ? `🔬 Submit ${modLabels.join(' + ')} Work`
                          : mods.code ? '🔬 Submit for Code Verification'
                          : mods.design ? '🎨 Submit for Design Review'
                          : '🚀 Submit for AQA Review'
                      }
                    </button>
                  </div>
                </div>
              );
            })()}

            {/* AQA Results */}
            {ms.aqa_result && (
              <AQAReport result={ms.aqa_result} milestoneIndex={i} milestone={ms} />
            )}
          </div>
        ))}
      </div>
    </motion.div>
  );
}
