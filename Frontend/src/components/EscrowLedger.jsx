import React, { useRef, useEffect, useState } from 'react';
import * as api from '../api';
import { motion, AnimatePresence } from 'framer-motion';
import { Wallet, CheckCircle2, Undo2, Link2, Coins, Pin, Lock, Unlock, ShieldCheck, ShieldAlert, List } from 'lucide-react';

const TYPE_COLORS = {
  DEPOSIT: 'var(--cyan)',
  PAYMENT: 'var(--green)',
  REFUND: 'var(--red)',
  STATE_CHANGE: 'var(--muted)',
};

const TYPE_ICONS = {
  DEPOSIT: <Wallet size={16} />,
  PAYMENT: <CheckCircle2 size={16} />,
  REFUND: <Undo2 size={16} />,
  STATE_CHANGE: <Link2 size={16} />,
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
        <h3 className="flex items-center gap-2"><Coins size={20} color="var(--cyan)" /> Escrow Ledger</h3>

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
          <button className="btn btn-sm btn-ghost flex items-center gap-1 mt-2" onClick={handleVerify} title="Verify chain integrity">
            <Lock size={14} /> Verify
          </button>
        )}

        {integrity && (
          <div className={`integrity-badge mt-2 ${integrity.valid ? 'valid' : 'invalid'}`}>
            {integrity.valid ? <span className="flex items-center gap-1"><ShieldCheck size={14} /> Chain Valid</span> : <span className="flex items-center gap-1"><ShieldAlert size={14} /> Broken at entry {integrity.broken_at_index}</span>}
            <span className="mono text-xs opacity-70"> ({integrity.total_entries} entries)</span>
          </div>
        )}
      </div>

      <div className="ledger-entries">
        {ledger.length === 0 ? (
          <div className="ledger-empty">
            <div className="empty-icon flex justify-center text-gray-500 mb-2"><List size={32} /></div>
            <p>No transactions yet</p>
            <p className="text-muted">Fund a project to see escrow activity</p>
          </div>
        ) : (
          <AnimatePresence>
            {[...ledger].reverse().map((entry, i) => (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
                key={entry.id || i}
                className="ledger-entry"
                style={{ borderLeftColor: TYPE_COLORS[entry.type] || 'var(--muted)' }}
              >
                <div className="entry-header">
                  <span className="entry-icon flex items-center">{TYPE_ICONS[entry.type] || <Pin size={16} />}</span>
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
                hx:{entry.tx_hash.slice(0, 8)}…{entry.tx_hash.slice(-8)}
              </div>
            </motion.div>
          ))}
          </AnimatePresence>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
