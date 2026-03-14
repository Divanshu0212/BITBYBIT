import React, { useState, useEffect } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';
import { motion } from 'framer-motion';
import { 
  Building2, BrainCircuit, Wallet, ClipboardCheck, ArrowLeft, 
  CheckCircle2, DollarSign, Clock, AlertTriangle, AlertCircle,
  MailCheck, UserCheck, XCircle, Package,
  HelpCircle, Send, ChevronRight, Sparkles
} from 'lucide-react';

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

function StepIndicator({ label, active, done }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {done ? (
        <CheckCircle2 size={16} style={{ color: 'var(--green)' }} />
      ) : active ? (
        <span className="spinner" style={{ width: 16, height: 16 }} />
      ) : (
        <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid var(--muted)' }} />
      )}
      <span style={{
        fontSize: 12, fontWeight: active ? 600 : 400,
        color: done ? 'var(--green)' : active ? 'var(--cyan)' : 'var(--muted)',
      }}>
        {label}
      </span>
    </div>
  );
}

export default function EmployerDashboard({ state, dispatch }) {
  const [description, setDescription] = useState('');
  const [budget, setBudget] = useState('');
  const [deadline, setDeadline] = useState('');
  const [phase, setPhase] = useState('list'); // 'list' | 'create' | 'review' | 'clarify' | 'fund' | 'proposals' | 'detail'
  const [selectedProject, setSelectedProject] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [decomposition, setDecomposition] = useState(null);
  const [proposalLoading, setProposalLoading] = useState({});

  const [clarifyQuestions, setClarifyQuestions] = useState([]);
  const [clarifyAnswers, setClarifyAnswers] = useState({});
  const [clarifyAssumptions, setClarifyAssumptions] = useState([]);
  const [progressStep, setProgressStep] = useState('');

  const isLoading = state.loading;

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

  const resetClarification = () => {
    setClarifyQuestions([]);
    setClarifyAnswers({});
    setClarifyAssumptions([]);
    setProgressStep('');
  };

  const handleCreateAndAnalyze = async () => {
    if (!description.trim()) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { create: true } });
    dispatch({ type: ACTIONS.SET_ERROR, payload: { create: null, decompose: null } });
    resetClarification();

    try {
      setProgressStep('creating');
      const project = await api.createProject({
        description,
        budget: budget ? parseFloat(budget) : undefined,
        deadline: deadline || undefined,
      });
      setSelectedProject(project);

      setProgressStep('analyzing');
      const clarity = await api.clarifyProject(project.id, description);

      if (clarity.needs_clarification && clarity.questions?.length > 0) {
        setClarifyQuestions(clarity.questions);
        setClarifyAssumptions(clarity.assumptions_if_unanswered || []);
        setPhase('clarify');
        dispatch({ type: ACTIONS.SET_LOADING, payload: { create: false } });
        setProgressStep('');
        await loadProjects();
        return;
      }

      setProgressStep('decomposing');
      dispatch({ type: ACTIONS.SET_LOADING, payload: { decompose: true } });
      const decomposed = await api.decomposeProject(project.id, description);
      setSelectedProject(decomposed);
      setDecomposition(decomposed.decomposition);
      setPhase('review');
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { create: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { create: false, decompose: false } });
      setProgressStep('');
    }
  };

  const handleSubmitClarificationAndDecompose = async () => {
    if (!selectedProject) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { decompose: true } });
    dispatch({ type: ACTIONS.SET_ERROR, payload: { decompose: null } });
    setProgressStep('decomposing');

    const answers = clarifyQuestions
      .filter(q => clarifyAnswers[q.id]?.trim())
      .map(q => ({
        question_id: q.id,
        question: q.question,
        answer: clarifyAnswers[q.id].trim(),
      }));

    try {
      const project = await api.decomposeProject(
        selectedProject.id,
        description || selectedProject.description,
        answers.length > 0 ? answers : null,
      );
      setSelectedProject(project);
      setDecomposition(project.decomposition);
      setPhase('review');
      resetClarification();
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { decompose: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { decompose: false } });
      setProgressStep('');
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

  const handlePublish = async () => {
    if (!selectedProject) return;
    dispatch({ type: ACTIONS.SET_LOADING, payload: { fund: true } });
    dispatch({ type: ACTIONS.SET_ERROR, payload: { fund: null } });
    try {
      const project = await api.publishProject(selectedProject.id);
      setSelectedProject(project);
      setPhase('proposals');
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { fund: err.message } });
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: { fund: false } });
    }
  };

  const loadProposals = async (projectId) => {
    try {
      const list = await api.listProjectProposals(projectId);
      setProposals(list);
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { proposals: err.message } });
    }
  };

  const handleAcceptProposal = async (proposalId) => {
    if (!selectedProject) return;
    setProposalLoading(prev => ({ ...prev, [proposalId]: 'accept' }));
    try {
      const project = await api.acceptProposal(selectedProject.id, proposalId);
      setSelectedProject(project);
      setPhase('detail');
      await loadProjects();
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { proposals: err.message } });
    } finally {
      setProposalLoading(prev => ({ ...prev, [proposalId]: null }));
    }
  };

  const handleRejectProposal = async (proposalId) => {
    if (!selectedProject) return;
    setProposalLoading(prev => ({ ...prev, [proposalId]: 'reject' }));
    try {
      await api.rejectProposal(selectedProject.id, proposalId);
      await loadProposals(selectedProject.id);
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: { proposals: err.message } });
    } finally {
      setProposalLoading(prev => ({ ...prev, [proposalId]: null }));
    }
  };

  const openProject = async (project) => {
    setSelectedProject(project);
    setDecomposition(project.decomposition);
    resetClarification();
    if (project.status === 'draft') {
      setDescription(project.description);
      setPhase('review');
    } else if (project.status === 'decomposed') {
      setDescription(project.description);
      setBudget(project.budget ? String(project.budget) : '');
      setPhase('review');
    } else if (project.status === 'funded' && !project.freelancer_id) {
      setPhase('proposals');
      await loadProposals(project.id);
    } else {
      setPhase('detail');
    }
  };

  const statusIcon = {
    draft: <ClipboardCheck size={16} />, 
    decomposed: <BrainCircuit size={16} />, 
    funded: <Wallet size={16} />, 
    active: <Building2 size={16} />, 
    completed: <CheckCircle2 size={16} />,
  };

  const statusColor = {
    draft: 'var(--muted)', decomposed: 'var(--cyan)', funded: 'var(--yellow)',
    active: 'var(--green)', completed: 'var(--green)',
  };

  const proposalStatusColor = (s) => ({
    pending: 'var(--yellow)', accepted: 'var(--green)', rejected: 'var(--red)',
  }[s] || 'var(--muted)');

  const pfiScoreColor = (s) => {
    if (s >= 70) return 'var(--green)';
    if (s >= 40) return 'var(--yellow)';
    return 'var(--red)';
  };

  // ── Project List View ─────────────────────────────────────────────────
  if (phase === 'list') {
    return (
      <div className="dashboard-panel">
        <div className="panel-header">
          <h2>🏢 My Projects</h2>
          <button className="btn btn-primary" onClick={() => {
            setPhase('create');
            setDescription('');
            setBudget('');
            setDeadline('');
            setSelectedProject(null);
            setDecomposition(null);
            resetClarification();
          }}>
            + Post a Project
          </button>
        </div>

        {state.errors.projects && (
          <div className="error-msg"><AlertCircle size={16} className="inline mr-1" /> {state.errors.projects}</div>
        )}

        {state.projects.length === 0 ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="empty-state">
            <div className="empty-icon"><ClipboardCheck size={48} className="mx-auto text-gray-400" /></div>
            <h3>No Projects Yet</h3>
            <p>Post your first project and let AI decompose it into milestones. Freelancers will send proposals!</p>
          </motion.div>
        ) : (
          <div className="project-grid">
            {state.projects.map(p => (
              <motion.div 
                whileHover={{ y: -5 }}
                key={p.id} 
                className="project-card" 
                onClick={() => openProject(p)}
              >
                <div className="project-card-header">
                  <span className="project-status flex items-center gap-1" style={{ color: statusColor[p.status], display: 'flex' }}>
                    {statusIcon[p.status]} {p.status.toUpperCase()}
                  </span>
                  {p.risk_level && (
                    <span className={`risk-badge risk-${(p.risk_level || 'medium').toLowerCase()}`}>
                      {p.risk_level}
                    </span>
                  )}
                </div>
                <p className="project-desc">{p.description.length > 120 ? p.description.slice(0, 120) + '…' : p.description}</p>
                <div className="project-card-footer flex items-center gap-3">
                  {p.budget && <span className="mono flex items-center gap-1"><DollarSign size={14} /> {p.budget.toLocaleString()}</span>}
                  {p.total_estimated_days && <span className="flex items-center gap-1"><Clock size={14} /> {p.total_estimated_days}d</span>}
                  <span className="flex items-center gap-1"><Package size={14} /> {p.milestones?.length || 0} milestones</span>
                  {p.status === 'funded' && !p.freelancer_id && (
                    <span style={{ color: 'var(--cyan)' }} className="flex items-center gap-1"><MailCheck size={14} /> Accepting Proposals</span>
                  )}
                  {p.freelancer_id && (
                    <span style={{ color: 'var(--green)' }} className="flex items-center gap-1"><UserCheck size={14} /> Freelancer Assigned</span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── Create / Review / Fund / Proposals / Detail Views ─────────────────
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="dashboard-panel">
      <div className="panel-header">
        <h2 className="flex items-center gap-2">
          <Building2 size={24} color="var(--cyan)" />
          {
          phase === 'create' ? 'Post a New Project' :
          phase === 'clarify' ? 'Clarify Your Project' :
          phase === 'proposals' ? 'Review Proposals' :
          phase === 'detail' ? 'Project Details' :
          'Project Setup'
        }</h2>
        <button className="btn btn-ghost flex items-center gap-1" onClick={() => { setPhase('list'); setSelectedProject(null); resetClarification(); }}>
          <ArrowLeft size={16} /> Back to Projects
        </button>
      </div>

      {/* Create Phase — One-click create + analyze */}
      {phase === 'create' && (
        <div className="form-section">
          <div className="form-group">
            <label className="input-label">Project Description</label>
            <textarea
              className="input-textarea"
              rows={5}
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Describe your project requirements in 2-4 sentences. Be specific about deliverables, technologies, and standards..."
              disabled={isLoading.create}
            />
          </div>

          {state.errors.create && <div className="error-msg flex items-center gap-1"><XCircle size={16} /> {state.errors.create}</div>}
          {state.errors.decompose && <div className="error-msg flex items-center gap-1"><XCircle size={16} /> {state.errors.decompose}</div>}

          {/* Progress indicator during one-click flow */}
          {(isLoading.create || isLoading.decompose) && progressStep && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="progress-steps"
              style={{
                display: 'flex', gap: 16, alignItems: 'center', padding: '14px 18px',
                background: 'var(--surface)', borderRadius: 10, marginBottom: 16, border: '1px solid var(--border)',
              }}
            >
              <StepIndicator label="Creating project" active={progressStep === 'creating'} done={progressStep !== 'creating'} />
              <ChevronRight size={14} style={{ color: 'var(--muted)' }} />
              <StepIndicator label="Analyzing clarity" active={progressStep === 'analyzing'} done={progressStep === 'decomposing'} />
              <ChevronRight size={14} style={{ color: 'var(--muted)' }} />
              <StepIndicator label="AI decomposition" active={progressStep === 'decomposing'} done={false} />
            </motion.div>
          )}

          <button
            className="btn btn-primary btn-lg flex items-center gap-2"
            onClick={handleCreateAndAnalyze}
            disabled={isLoading.create || isLoading.decompose || !description.trim()}
          >
            {(isLoading.create || isLoading.decompose)
              ? <><span className="spinner" /> {progressStep === 'creating' ? 'Creating...' : progressStep === 'analyzing' ? 'Analyzing clarity...' : 'Decomposing with AI...'}</>
              : <><Sparkles size={18} /> Create & Decompose</>
            }
          </button>
        </div>
      )}

      {/* Clarification Phase — Questions for vague descriptions */}
      {phase === 'clarify' && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="form-section">
          <div className="clarify-banner" style={{
            background: 'linear-gradient(135deg, rgba(var(--cyan-rgb, 0,188,212), 0.08), rgba(var(--yellow-rgb, 255,193,7), 0.06))',
            border: '1px solid rgba(var(--cyan-rgb, 0,188,212), 0.25)',
            borderRadius: 12, padding: '20px 24px', marginBottom: 20,
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
              <HelpCircle size={22} style={{ color: 'var(--cyan)', flexShrink: 0, marginTop: 2 }} />
              <div>
                <h3 style={{ margin: 0, fontSize: 16, color: 'var(--text)' }}>A few questions to improve your decomposition</h3>
                <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)' }}>
                  Your description could use some more detail. Answer these questions so the AI can create better, more accurate milestones.
                  You can skip any questions — the AI will make reasonable assumptions.
                </p>
              </div>
            </div>
          </div>

          <div className="project-desc-preview" style={{
            background: 'var(--surface)', borderRadius: 8, padding: '12px 16px',
            marginBottom: 20, border: '1px solid var(--border)', fontSize: 13, color: 'var(--muted)',
          }}>
            <strong style={{ color: 'var(--text)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Your description:
            </strong>
            <p style={{ margin: '6px 0 0' }}>{selectedProject?.description}</p>
          </div>

          <div className="clarify-questions" style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 24 }}>
            {clarifyQuestions.map((q, i) => (
              <motion.div
                key={q.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                style={{
                  background: 'var(--surface)', borderRadius: 10, padding: '16px 18px',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
                  <span style={{
                    background: 'var(--cyan)', color: '#000', borderRadius: 6, padding: '2px 8px',
                    fontSize: 11, fontWeight: 700, flexShrink: 0,
                  }}>Q{i + 1}</span>
                  <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontWeight: 500, color: 'var(--text)', fontSize: 14 }}>{q.question}</p>
                    {q.reason && (
                      <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--muted)', fontStyle: 'italic' }}>{q.reason}</p>
                    )}
                  </div>
                </div>
                <textarea
                  className="input-textarea"
                  rows={2}
                  placeholder="Type your answer... (leave empty to skip)"
                  value={clarifyAnswers[q.id] || ''}
                  onChange={e => setClarifyAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                  style={{ marginTop: 4, fontSize: 13 }}
                />
              </motion.div>
            ))}
          </div>

          {clarifyAssumptions.length > 0 && (
            <div style={{
              background: 'var(--surface)', borderRadius: 8, padding: '12px 16px',
              marginBottom: 20, border: '1px solid var(--border)',
            }}>
              <strong style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Assumptions if unanswered:
              </strong>
              <ul style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 13, color: 'var(--muted)' }}>
                {clarifyAssumptions.map((a, i) => <li key={i} style={{ marginBottom: 4 }}>{a}</li>)}
              </ul>
            </div>
          )}

          {state.errors.decompose && <div className="error-msg flex items-center gap-1"><XCircle size={16} /> {state.errors.decompose}</div>}

          {isLoading.decompose && progressStep === 'decomposing' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="progress-steps"
              style={{
                display: 'flex', gap: 16, alignItems: 'center', padding: '14px 18px',
                background: 'var(--surface)', borderRadius: 10, marginBottom: 16, border: '1px solid var(--border)',
              }}
            >
              <StepIndicator label="Answers submitted" active={false} done={true} />
              <ChevronRight size={14} style={{ color: 'var(--muted)' }} />
              <StepIndicator label="AI decomposition" active={true} done={false} />
            </motion.div>
          )}

          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className="btn btn-primary btn-lg flex items-center gap-2"
              onClick={handleSubmitClarificationAndDecompose}
              disabled={isLoading.decompose}
            >
              {isLoading.decompose
                ? <><span className="spinner" /> Decomposing with your answers...</>
                : <><Send size={16} /> Submit & Decompose</>
              }
            </button>
            <button
              className="btn btn-ghost flex items-center gap-2"
              onClick={() => {
                resetClarification();
                handleDecompose().then(() => {
                  setPhase('review');
                });
              }}
              disabled={isLoading.decompose}
            >
              Skip — Decompose Anyway
            </button>
          </div>
        </motion.div>
      )}

      {/* Review Phase — Milestones display */}
      {phase === 'review' && (
        <>
          <div className="form-section">
            <div className="form-group">
              <label className="input-label">Project Description</label>
              <textarea
                className="input-textarea"
                rows={5}
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Describe your project requirements in 2-4 sentences. Be specific about deliverables, technologies, and standards..."
                disabled={selectedProject && selectedProject.status !== 'draft'}
              />
            </div>

            {state.errors.decompose && <div className="error-msg flex items-center gap-1"><XCircle size={16} /> {state.errors.decompose}</div>}

            {selectedProject && (!selectedProject.milestones || selectedProject.milestones.length === 0) && (
              <button
                className="btn btn-primary btn-lg flex items-center gap-2"
                onClick={handleDecompose}
                disabled={isLoading.decompose}
              >
                {isLoading.decompose ? <><span className="spinner" /> AI is analyzing your project...</> : <><BrainCircuit size={18} /> Decompose with AI</>}
              </button>
            )}
          </div>

          {selectedProject && selectedProject.milestones?.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="animate-fade-in">
              <div className="decomp-meta flex items-center gap-3">
                <span className={`risk-badge flex items-center gap-1 risk-${(selectedProject.risk_level || 'medium').toLowerCase()}`}>
                  <AlertTriangle size={14} /> {selectedProject.risk_level || 'Medium'} Risk
                </span>
                <span className="meta-tag flex items-center gap-1"><Clock size={14} /> {selectedProject.total_estimated_days || '?'} days estimated</span>
                <span className="meta-tag flex items-center gap-1"><Package size={14} /> {selectedProject.milestones.length} milestones</span>
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
                      {ms.task_type && <span className={`task-type-badge ${ms.task_type}`}>{ms.task_type}</span>}
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

              {/* Publish Section */}
              {selectedProject.status === 'decomposed' && (
                <div className="confirm-section">
                  <h3>📢 Publish for Proposals</h3>
                  <p className="text-muted" style={{ marginBottom: 16 }}>
                    Once published, freelancers can browse your project and submit proposals with their bid amounts.
                    Funds are locked in escrow only when you accept a proposal — the amount blocked will be the freelancer's bid.
                  </p>
                  {state.errors.fund && <div className="error-msg flex items-center gap-1"><XCircle size={16} /> {state.errors.fund}</div>}
                  <div className="btn-row">
                    <button className="btn btn-ghost" onClick={() => { handleDecompose(); }}>
                      ← Re-decompose
                    </button>
                    <button
                      className="btn btn-primary btn-lg"
                      onClick={handlePublish}
                      disabled={isLoading.fund}
                    >
                      {isLoading.fund ? <><span className="spinner" /> Publishing...</> : '📢 Publish for Proposals'}
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </>
      )}

      {/* ── Proposals Phase ─────────────────────────────────────────────── */}
      {phase === 'proposals' && selectedProject && (
        <div className="animate-fade-in">
          <div className="success-banner" style={{ marginBottom: 24 }}>
            <div className="success-icon">📢</div>
            <h3>Project Published — Accepting Proposals</h3>
            <p>Your project is live! Freelancers can now browse and submit proposals. When you accept a proposal, the freelancer's bid amount will be locked in escrow.</p>
          </div>

          {/* Project summary mini */}
          <div className="project-summary-mini">
            <p className="project-desc">{selectedProject.description.length > 200 ? selectedProject.description.slice(0, 200) + '…' : selectedProject.description}</p>
            <div className="project-card-footer">
              {selectedProject.total_estimated_days && <span>📅 {selectedProject.total_estimated_days} days</span>}
              <span>📦 {selectedProject.milestones?.length || 0} milestones</span>
              {selectedProject.risk_level && (
                <span className={`risk-badge risk-${selectedProject.risk_level.toLowerCase()}`}>
                  {selectedProject.risk_level}
                </span>
              )}
            </div>
          </div>

          <div className="proposals-section-header">
            <h3>📨 Proposals ({proposals.length})</h3>
            <button className="btn btn-sm btn-ghost" onClick={() => loadProposals(selectedProject.id)}>
              🔄 Refresh
            </button>
          </div>

          {state.errors.proposals && <div className="error-msg">❌ {state.errors.proposals}</div>}

          {proposals.length === 0 ? (
            <div className="empty-state" style={{ padding: '40px 20px' }}>
              <div className="empty-icon">📨</div>
              <h3>No Proposals Yet</h3>
              <p>Freelancers haven't submitted proposals yet. Your project is listed in their "Find Work" page.</p>
              <button className="btn btn-accent" onClick={() => loadProposals(selectedProject.id)}>
                🔄 Check for New Proposals
              </button>
            </div>
          ) : (
            <div className="employer-proposals-list">
              {proposals.map(prop => (
                <div key={prop.id} className={`employer-proposal-card proposal-${prop.status}`}>
                  <div className="ep-header">
                    <div className="ep-freelancer-info">
                      <div className="ep-avatar">
                        {prop.freelancer_name?.[0]?.toUpperCase() || '?'}
                      </div>
                      <div className="ep-name-block">
                        <h4>{prop.freelancer_name || 'Freelancer'}</h4>
                        <span className="ep-email">{prop.freelancer_email}</span>
                      </div>
                    </div>
                    <div className="ep-badges">
                      <span className="pfi-mini-badge" style={{
                        color: pfiScoreColor(prop.freelancer_pfi_score || 50),
                        borderColor: pfiScoreColor(prop.freelancer_pfi_score || 50),
                      }}>
                        PFI: {prop.freelancer_pfi_score || 50}
                      </span>
                      <span className="proposal-status-badge" style={{
                        color: proposalStatusColor(prop.status),
                        borderColor: proposalStatusColor(prop.status),
                      }}>
                        {prop.status === 'pending' ? '⏳' : prop.status === 'accepted' ? '✅' : '❌'} {prop.status.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  {/* Skills */}
                  {prop.freelancer_skills && prop.freelancer_skills.length > 0 && (
                    <div className="ep-skills">
                      {prop.freelancer_skills.map((s, i) => (
                        <span key={i} className="skill-tag">{s}</span>
                      ))}
                    </div>
                  )}

                  {/* Bio */}
                  {prop.freelancer_bio && (
                    <p className="ep-bio">{prop.freelancer_bio.length > 120 ? prop.freelancer_bio.slice(0, 120) + '…' : prop.freelancer_bio}</p>
                  )}

                  {/* Cover Letter */}
                  <div className="ep-cover-letter">
                    <strong>Cover Letter:</strong>
                    <p>{prop.cover_letter}</p>
                  </div>

                  {/* Bid details */}
                  <div className="ep-bid-details">
                    {prop.bid_amount != null && (
                      <div className="ep-bid-item">
                        <span className="ep-bid-label">Bid Amount</span>
                        <span className="ep-bid-value mono">${prop.bid_amount.toLocaleString()}</span>
                      </div>
                    )}
                    {prop.estimated_days != null && (
                      <div className="ep-bid-item">
                        <span className="ep-bid-label">Est. Delivery</span>
                        <span className="ep-bid-value">{prop.estimated_days} days</span>
                      </div>
                    )}
                    <div className="ep-bid-item">
                      <span className="ep-bid-label">Submitted</span>
                      <span className="ep-bid-value mono">{new Date(prop.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  {prop.status === 'pending' && (
                    <div className="ep-actions">
                      <button
                        className="btn btn-primary"
                        onClick={() => handleAcceptProposal(prop.id)}
                        disabled={!!proposalLoading[prop.id]}
                      >
                        {proposalLoading[prop.id] === 'accept'
                          ? <><span className="spinner" /> Accepting...</>
                          : '✅ Accept & Assign'
                        }
                      </button>
                      <button
                        className="btn btn-ghost"
                        onClick={() => handleRejectProposal(prop.id)}
                        disabled={!!proposalLoading[prop.id]}
                      >
                        {proposalLoading[prop.id] === 'reject'
                          ? <><span className="spinner" /> Rejecting...</>
                          : '❌ Decline'
                        }
                      </button>
                    </div>
                  )}

                  {prop.status === 'accepted' && (
                    <div className="ep-accepted-banner">
                      🎉 Proposal accepted — freelancer has been assigned to the project!
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Detail View ─────────────────────────────────────────────────── */}
      {phase === 'detail' && selectedProject && (
        <div className="animate-fade-in">
          <div className="project-detail-header">
            <span className="project-status" style={{ color: statusColor[selectedProject.status] }}>
              {statusIcon[selectedProject.status]} {selectedProject.status.toUpperCase()}
            </span>
            {selectedProject.budget && <span className="mono">💰 ${selectedProject.budget.toLocaleString()}</span>}
            {selectedProject.freelancer_id && (
              <span style={{ color: 'var(--green)', fontSize: '12px' }}>👤 Freelancer Assigned</span>
            )}
          </div>
          <p className="project-desc">{selectedProject.description}</p>

          <div className="milestone-cards">
            {(selectedProject.milestones || []).map((ms, i) => (
              <div key={ms.id} className={`milestone-card ${ms.status === 'PAID_FULL' ? 'status-success' : ms.status === 'REFUND_INITIATED' ? 'status-danger' : ''}`}>
                <div className="ms-card-header">
                  <span className="ms-index">M{i + 1}</span>
                  <h4>{ms.title}</h4>
                  {ms.task_type && <span className={`task-type-badge ${ms.task_type}`}>{ms.task_type}</span>}
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
    </motion.div>
  );
}
