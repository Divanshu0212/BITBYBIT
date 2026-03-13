import React, { useState } from 'react';
import { ACTIONS } from '../store/actions';

export default function SettingsModal({ state, dispatch, onClose }) {
  const [key, setKey] = useState(state.apiKey || '');
  const [showKey, setShowKey] = useState(false);

  const handleSave = () => {
    if (!key.trim()) return;
    localStorage.setItem('bitbybit_api_key', key.trim());
    dispatch({ type: ACTIONS.SET_API_KEY, payload: key.trim() });
    if (onClose) onClose();
  };

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <div className="modal-icon">⚙</div>
          <h2>Configuration</h2>
          <p className="modal-subtitle">Enter your Groq API key to power AI features</p>
        </div>
        <div className="modal-body">
          <label className="input-label">Groq API Key</label>
          <div className="api-key-input-row">
            <input
              type={showKey ? 'text' : 'password'}
              value={key}
              onChange={e => setKey(e.target.value)}
              placeholder="AIza..."
              className="input-field mono"
              autoFocus
            />
            <button
              className="btn-icon"
              onClick={() => setShowKey(!showKey)}
              title={showKey ? 'Hide' : 'Show'}
            >
              {showKey ? '🙈' : '👁'}
            </button>
          </div>
          <p className="input-hint">
            Get your key at{' '}
            <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">
              console.groq.com/keys
            </a>
          </p>
        </div>
        <div className="modal-footer">
          {state.apiKey && (
            <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          )}
          <button className="btn btn-primary" onClick={handleSave} disabled={!key.trim()}>
            Save &amp; Continue
          </button>
        </div>
      </div>
    </div>
  );
}
