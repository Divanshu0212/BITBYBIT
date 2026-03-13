import React, { useRef, useEffect, useState } from 'react';
import * as api from '../api';

const TYPE_COLORS = {
  DEPOSIT: 'var(--cyan)',
  PAYMENT: 'var(--green)',
  REFUND: 'var(--red)',
  STATE_CHANGE: 'var(--muted)',
};

const TYPE_ICONS = {
  DEPOSIT: '💰',
  PAYMENT: '✅',
  REFUND: '🔄',
  STATE_CHANGE: '🔗',
};

export default function EscrowLedger({ state, dispatch }) {
  const bottomRef = useRef(null);
  const [escrow, setEscrow] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [integrity, setIntegrity] = useState(null);
  const [selectedProjectId, setSelectedProjectId] = useState(null);

  const projects = state.projects || [];

  // Auto-select first project with escrow
  useEffect(() => {
    const funded = projects.find(p => ['funded', 'active', 'completed'].includes(p.status));
    if (funded && !selectedProjectId) {
      setSelectedProjectId(funded.id);
    }
  }, [projects]);

  // Load escrow when project changes
  useEffect(() => {
    if (selectedProjectId) {
      loadEscrow(selectedProjectId);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [ledger.length]);

  const loadEscrow = async (projectId) => {
    try {
      const [escrowData, ledgerData] = await Promise.all([
        api.getEscrow(projectId),
        api.getLedger(projectId),
      ]);
      setEscrow(escrowData);
      setLedger(ledgerData.entries || []);
    } catch {
      setEscrow(null);
      setLedger([]);
    }
  };

  const handleVerify = async () => {
    if (!selectedProjectId) return;
    try {
      const result = await api.verifyLedgerIntegrity(selectedProjectId);
      setIntegrity(result);
    } catch {
      setIntegrity({ valid: false, error: 'Failed to verify' });
    }
  };

  const formatTime = (iso) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false }) + '.' +
      String(d.getMilliseconds()).padStart(3, '0');
  };

  return (
    <div className="ledger-panel">
      <div className="ledger-header">
        <h3>⛓ Escrow Ledger</h3>

        {/* Project selector */}
        {projects.length > 1 && (
          <select className="input-field ledger-select"
            value={selectedProjectId || ''}
            onChange={e => setSelectedProjectId(e.target.value)}>
            {projects.filter(p => ['funded', 'active', 'completed'].includes(p.status)).map(p => (
              <option key={p.id} value={p.id}>{p.description.slice(0, 40)}...</option>
            ))}
          </select>
        )}

        {escrow && (
          <div className="ledger-summary">
            <div className="ledger-stat">
              <span className="stat-label">Locked</span>
              <span className="stat-value cyan">${escrow.locked_funds?.toLocaleString() || '0'}</span>
            </div>
            <div className="ledger-stat">
              <span className="stat-label">Released</span>
              <span className="stat-value green">${escrow.released_funds?.toLocaleString() || '0'}</span>
            </div>
            <div className="ledger-stat">
              <span className="stat-label">Refunded</span>
              <span className="stat-value red">${escrow.refunded_funds?.toLocaleString() || '0'}</span>
            </div>
          </div>
        )}
        {escrow && (
          <div className={`contract-state-badge state-${escrow.state?.toLowerCase().replace(/_/g, '-')}`}>
            {escrow.state}
          </div>
        )}

        {escrow && (
          <button className="btn btn-sm btn-ghost" onClick={handleVerify} title="Verify chain integrity">
            🔐 Verify
          </button>
        )}

        {integrity && (
          <div className={`integrity-badge ${integrity.valid ? 'valid' : 'invalid'}`}>
            {integrity.valid ? '✅ Chain Valid' : `❌ Broken at entry ${integrity.broken_at_index}`}
            <span className="mono"> ({integrity.total_entries} entries)</span>
          </div>
        )}
      </div>

      <div className="ledger-entries">
        {ledger.length === 0 ? (
          <div className="ledger-empty">
            <div className="empty-icon">📋</div>
            <p>No transactions yet</p>
            <p className="text-muted">Fund a project to see escrow activity</p>
          </div>
        ) : (
          ledger.map((entry, i) => (
            <div
              key={entry.id || i}
              className="ledger-entry animate-slide-in"
              style={{ borderLeftColor: TYPE_COLORS[entry.type] || 'var(--muted)' }}
            >
              <div className="entry-header">
                <span className="entry-icon">{TYPE_ICONS[entry.type] || '📌'}</span>
                <span className="entry-event" style={{ color: TYPE_COLORS[entry.type] }}>
                  {entry.event}
                </span>
                {entry.amount != null && (
                  <span className="entry-amount" style={{ color: TYPE_COLORS[entry.type] }}>
                    ${entry.amount.toLocaleString()}
                  </span>
                )}
              </div>
              <div className="entry-details">{entry.details}</div>
              <div className="entry-time mono">{formatTime(entry.timestamp)}</div>
              <div className="entry-hash mono" title={entry.tx_hash}>
                0x{entry.tx_hash?.slice(0, 12)}…
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
