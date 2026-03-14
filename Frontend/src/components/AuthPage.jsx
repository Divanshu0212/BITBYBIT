import React, { useState } from 'react';
import { ACTIONS } from '../store/actions';
import * as api from '../api';

export default function AuthPage({ dispatch }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [role, setRole] = useState('employer');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [skills, setSkills] = useState('');
  const [bio, setBio] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let data;
      if (mode === 'login') {
        data = await api.login({ email, password });
      } else {
        const skillsList = skills.split(',').map(s => s.trim()).filter(Boolean);
        data = await api.register({
          email, password, name, role,
          skills: role === 'freelancer' ? skillsList : undefined,
          bio: role === 'freelancer' ? bio : undefined,
        });
      }
      dispatch({ type: ACTIONS.SET_TOKEN, payload: data.access_token });
      dispatch({ type: ACTIONS.SET_USER, payload: data.user });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-bg-grid" />
      <div className="auth-container">
        <div className="auth-header">
          <div className="auth-logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">Snack Overflow</span>
          </div>
          <p className="auth-tagline">Autonomous AI Project & Payment Intermediary</p>
        </div>

        <div className="auth-card">
          <div className="auth-tabs">
            <button
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => { setMode('login'); setError(null); }}
            >
              Sign In
            </button>
            <button
              className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
              onClick={() => { setMode('register'); setError(null); }}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {mode === 'register' && (
              <>
                <div className="form-group">
                  <label className="input-label">Full Name</label>
                  <input
                    type="text" className="input-field" value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="John Doe" required
                  />
                </div>

                <div className="form-group">
                  <label className="input-label">I am a...</label>
                  <div className="role-selector">
                    <button type="button"
                      className={`role-btn ${role === 'employer' ? 'active' : ''}`}
                      onClick={() => setRole('employer')}
                    >
                      <span className="role-icon">🏢</span>
                      <span className="role-label">Employer</span>
                      <span className="role-desc">Post projects & manage freelancers</span>
                    </button>
                    <button type="button"
                      className={`role-btn ${role === 'freelancer' ? 'active' : ''}`}
                      onClick={() => setRole('freelancer')}
                    >
                      <span className="role-icon">👩‍💻</span>
                      <span className="role-label">Freelancer</span>
                      <span className="role-desc">Work on projects & build reputation</span>
                    </button>
                  </div>
                </div>
              </>
            )}

            <div className="form-group">
              <label className="input-label">Email</label>
              <input
                type="email" className="input-field" value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com" required
              />
            </div>

            <div className="form-group">
              <label className="input-label">Password</label>
              <input
                type="password" className="input-field" value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" required minLength={6}
              />
            </div>

            {mode === 'register' && role === 'freelancer' && (
              <>
                <div className="form-group">
                  <label className="input-label">Skills (comma-separated)</label>
                  <input
                    type="text" className="input-field" value={skills}
                    onChange={e => setSkills(e.target.value)}
                    placeholder="React, Python, UI/UX Design"
                  />
                </div>
                <div className="form-group">
                  <label className="input-label">Bio</label>
                  <textarea
                    className="input-textarea" rows={3} value={bio}
                    onChange={e => setBio(e.target.value)}
                    placeholder="Tell employers about your experience..."
                  />
                </div>
              </>
            )}

            {error && <div className="error-msg">❌ {error}</div>}

            <button
              type="submit"
              className="btn btn-primary btn-lg auth-submit"
              disabled={loading}
            >
              {loading ? (
                <><span className="spinner" /> {mode === 'login' ? 'Signing in...' : 'Creating account...'}</>
              ) : (
                mode === 'login' ? '🔐 Sign In' : '🚀 Create Account'
              )}
            </button>
          </form>
        </div>

        <div className="auth-features">
          <div className="auth-feature">
            <span className="feature-icon">🤖</span>
            <span>AI-Powered Quality Assurance</span>
          </div>
          <div className="auth-feature">
            <span className="feature-icon">🔒</span>
            <span>Secure Escrow Payments</span>
          </div>
          <div className="auth-feature">
            <span className="feature-icon">📊</span>
            <span>Merit-Based PFI Scoring</span>
          </div>
        </div>
      </div>
    </div>
  );
}
