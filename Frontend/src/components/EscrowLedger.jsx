import React, { useRef, useEffect } from 'react';

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

export default function EscrowLedger({ ledger, escrow }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [ledger.length]);

  const formatTime = (iso) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false }) + '.' +
      String(d.getMilliseconds()).padStart(3, '0');
  };

  return (
    <div className="ledger-panel">
      <div className="ledger-header">
        <h3>⛓ Blockchain Ledger</h3>
        {escrow && (
          <div className="ledger-summary">
            <div className="ledger-stat">
              <span className="stat-label">Locked</span>
              <span className="stat-value cyan">${escrow.lockedFunds?.toLocaleString() || '0'}</span>
            </div>
            <div className="ledger-stat">
              <span className="stat-label">Released</span>
              <span className="stat-value green">${escrow.releasedFunds?.toLocaleString() || '0'}</span>
            </div>
            <div className="ledger-stat">
              <span className="stat-label">Refunded</span>
              <span className="stat-value red">${escrow.refundedFunds?.toLocaleString() || '0'}</span>
            </div>
          </div>
        )}
        {escrow && (
          <div className={`contract-state-badge state-${escrow.state?.toLowerCase().replace(/_/g, '-')}`}>
            {escrow.state}
          </div>
        )}
      </div>

      <div className="ledger-entries">
        {ledger.length === 0 ? (
          <div className="ledger-empty">
            <div className="empty-icon">📋</div>
            <p>No transactions yet</p>
            <p className="text-muted">Create a project to begin</p>
          </div>
        ) : (
          ledger.map((entry, i) => (
            <div
              key={i}
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
              <div className="entry-hash mono">
                {`0x${(i * 7919 + 0xABCDEF).toString(16).slice(0, 12)}`}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
