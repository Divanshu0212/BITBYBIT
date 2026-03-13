// api.js — Centralized API client for BITBYBIT backend
// All backend calls go through this module. JWT token is auto-attached.

const API_BASE = 'http://localhost:8000/api';

// ── Token Management ────────────────────────────────────────────────────

let _token = localStorage.getItem('bitbybit_token') || null;

export function setToken(token) {
  _token = token;
  if (token) {
    localStorage.setItem('bitbybit_token', token);
  } else {
    localStorage.removeItem('bitbybit_token');
  }
}

export function getToken() {
  return _token;
}

export function clearAuth() {
  _token = null;
  localStorage.removeItem('bitbybit_token');
  localStorage.removeItem('bitbybit_user');
}

// ── Core Fetch Wrapper ──────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (_token) {
    headers['Authorization'] = `Bearer ${_token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 204) return null;

  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail || data?.message || `API error ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }

  return data;
}

// ── Auth ─────────────────────────────────────────────────────────────────

export async function register({ email, password, name, role, skills, bio }) {
  const body = { email, password, name, role };
  if (role === 'freelancer') {
    if (skills) body.skills = skills;
    if (bio) body.bio = bio;
  }
  const data = await apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  setToken(data.access_token);
  localStorage.setItem('bitbybit_user', JSON.stringify(data.user));
  return data;
}

export async function login({ email, password }) {
  const data = await apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  localStorage.setItem('bitbybit_user', JSON.stringify(data.user));
  return data;
}

export async function getMe() {
  return await apiFetch('/auth/me');
}

// ── Employer ─────────────────────────────────────────────────────────────

export async function createProject({ description, budget, deadline }) {
  const body = { description };
  if (budget) body.budget = budget;
  if (deadline) body.deadline = deadline;
  return await apiFetch('/employer/projects', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function listEmployerProjects() {
  return await apiFetch('/employer/projects');
}

export async function getEmployerProject(projectId) {
  return await apiFetch(`/employer/projects/${projectId}`);
}

export async function decomposeProject(projectId, description) {
  return await apiFetch(`/employer/projects/${projectId}/decompose`, {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}

export async function fundProject(projectId, amount) {
  return await apiFetch(`/employer/projects/${projectId}/fund`, {
    method: 'POST',
    body: JSON.stringify({ amount }),
  });
}

export async function assignFreelancer(projectId, freelancerId) {
  return await apiFetch(`/employer/projects/${projectId}/assign/${freelancerId}`, {
    method: 'POST',
  });
}

export async function listFreelancers() {
  return await apiFetch('/employer/freelancers');
}

export async function getProjectHITL(projectId) {
  return await apiFetch(`/employer/projects/${projectId}/hitl`);
}

export async function resolveHITL(projectId, milestoneId, action, reason) {
  return await apiFetch(`/employer/projects/${projectId}/hitl/${milestoneId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
  });
}

export async function getEmployerAnalytics() {
  return await apiFetch('/employer/analytics');
}

// ── Freelancer ───────────────────────────────────────────────────────────

export async function listFreelancerProjects() {
  return await apiFetch('/freelancer/projects');
}

export async function getFreelancerProject(projectId) {
  return await apiFetch(`/freelancer/projects/${projectId}`);
}

export async function activateMilestone(projectId, milestoneId) {
  return await apiFetch(`/freelancer/projects/${projectId}/milestones/${milestoneId}/activate`, {
    method: 'POST',
  });
}

export async function submitWork(projectId, milestoneId, submissionText, submissionUrl) {
  const body = { submission_text: submissionText };
  if (submissionUrl) body.submission_url = submissionUrl;
  return await apiFetch(`/freelancer/projects/${projectId}/milestones/${milestoneId}/submit`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getOwnPFI() {
  return await apiFetch('/freelancer/pfi');
}

export async function getOwnPFIHistory() {
  return await apiFetch('/freelancer/pfi/history');
}

// ── Escrow ───────────────────────────────────────────────────────────────

export async function getEscrow(projectId) {
  return await apiFetch(`/escrow/projects/${projectId}`);
}

export async function getLedger(projectId) {
  return await apiFetch(`/escrow/projects/${projectId}/ledger`);
}

export async function verifyLedgerIntegrity(projectId) {
  return await apiFetch(`/escrow/projects/${projectId}/verify`);
}

// ── PFI ──────────────────────────────────────────────────────────────────

export async function getPFIScore(userId) {
  return await apiFetch(`/pfi/scores/${userId}`);
}

export async function getLeaderboard(limit = 50) {
  return await apiFetch(`/pfi/leaderboard?limit=${limit}`);
}

export async function getPFIHistory(userId) {
  return await apiFetch(`/pfi/history/${userId}`);
}

// ── AI ───────────────────────────────────────────────────────────────────

export async function aiDecompose(description) {
  return await apiFetch('/ai/decompose', {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}

export async function aiEvaluate(data) {
  return await apiFetch('/ai/evaluate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function aiGenerateDemo() {
  return await apiFetch('/ai/demo', {
    method: 'POST',
  });
}

export async function aiScoreMatch(skills, domain) {
  return await apiFetch('/ai/score-match', {
    method: 'POST',
    body: JSON.stringify({ skills, domain }),
  });
}

export async function aiDetectBias(ratingHistory) {
  return await apiFetch('/ai/detect-bias', {
    method: 'POST',
    body: JSON.stringify({ rating_history: ratingHistory }),
  });
}
