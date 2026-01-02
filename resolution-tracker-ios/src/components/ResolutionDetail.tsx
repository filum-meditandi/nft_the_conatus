import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useResolutionStore } from '../store/resolutionStore';
import { format } from 'date-fns';
import { MOODS } from '../types';

function ResolutionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    currentResolution,
    logs,
    summary,
    selectResolution,
    verifyChain,
    updateStatus,
    deleteResolution,
    isLoading,
  } = useResolutionStore();

  const [chainVerified, setChainVerified] = useState<boolean | null>(null);
  const [showActions, setShowActions] = useState(false);

  useEffect(() => {
    if (id) {
      selectResolution(id);
    }
  }, [id, selectResolution]);

  useEffect(() => {
    if (id && currentResolution) {
      verifyChain(id).then(setChainVerified);
    }
  }, [id, currentResolution, verifyChain, logs]);

  const shortHash = (hash: string) => hash.slice(0, 12) + '...';

  const getMoodEmoji = (mood: string) => {
    const found = MOODS.find((m) => m.value === mood);
    return found?.emoji || '😐';
  };

  const handleStatusChange = async (newStatus: string) => {
    if (id) {
      await updateStatus(id, newStatus);
      setShowActions(false);
    }
  };

  const handleDelete = async () => {
    if (id && window.confirm('Are you sure you want to delete this resolution?')) {
      await deleteResolution(id);
      navigate('/');
    }
  };

  if (isLoading || !currentResolution) {
    return (
      <div className="loading" style={{ height: '100vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div>
      <header className="header">
        <button className="back-button" onClick={() => navigate('/')}>
          ← Back
        </button>
        <h1>Details</h1>
        <button
          className="back-button"
          onClick={() => setShowActions(!showActions)}
          style={{ color: 'var(--text-secondary)' }}
        >
          •••
        </button>
      </header>

      {showActions && (
        <div className="page" style={{ paddingBottom: 0 }}>
          <div className="card">
            <button
              className="btn btn-secondary"
              style={{ marginBottom: '8px' }}
              onClick={() => handleStatusChange('completed')}
            >
              Mark as Completed
            </button>
            <button
              className="btn btn-secondary"
              style={{ marginBottom: '8px' }}
              onClick={() => handleStatusChange('paused')}
            >
              Pause Resolution
            </button>
            <button className="btn btn-danger" onClick={handleDelete}>
              Delete Resolution
            </button>
          </div>
        </div>
      )}

      <div className="page" style={{ paddingBottom: '160px' }}>
        {/* Resolution Info */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title" style={{ fontSize: '1.5rem' }}>
                {currentResolution.title}
              </h2>
              <p className="card-subtitle">{currentResolution.description}</p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <span className="resolution-category">{currentResolution.category}</span>
            <div className={`status-indicator status-${currentResolution.status}`}>
              <span className="status-dot"></span>
              <span style={{ textTransform: 'capitalize' }}>
                {currentResolution.status}
              </span>
            </div>
          </div>

          {/* NFT Info */}
          <div className="nft-badge">
            <span className="nft-badge-icon">🔗</span>
            <div style={{ flex: 1 }}>
              <div className="nft-label">Genesis Hash (Token ID)</div>
              <div className="nft-hash">{shortHash(currentResolution.genesis_hash)}</div>
            </div>
          </div>

          <div
            className={`verification-badge ${chainVerified === false ? 'invalid' : ''}`}
          >
            {chainVerified === null ? (
              'Verifying chain...'
            ) : chainVerified ? (
              <>✓ Chain Integrity Verified</>
            ) : (
              <>⚠ Chain Integrity Failed</>
            )}
          </div>
        </div>

        {/* Stats */}
        {summary && (
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-value">{summary.current_streak}</div>
              <div className="stat-card-label">Current Streak</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-value">{summary.longest_streak}</div>
              <div className="stat-card-label">Longest Streak</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-value">{summary.total_logs}</div>
              <div className="stat-card-label">Total Logs</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-value">
                {summary.average_progress.toFixed(1)}/10
              </div>
              <div className="stat-card-label">Avg Progress</div>
            </div>
          </div>
        )}

        {/* Hash Chain Visualization */}
        <div className="card">
          <div className="hash-chain-title">
            <span>🔗</span>
            Attestation Chain ({currentResolution.attestation_count} entries)
          </div>

          <div className="chain-item">
            <div className="chain-dot" style={{ background: 'var(--success)' }}></div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Genesis Block
              </div>
              <div className="chain-hash">
                {currentResolution.genesis_hash.slice(0, 32)}...
              </div>
            </div>
          </div>

          {logs.slice(-3).map((log, index) => (
            <div key={log.id} className="chain-item">
              <div className="chain-dot"></div>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Log #{logs.length - 2 + index} - {log.date}
                </div>
                <div className="chain-hash">{log.hash.slice(0, 32)}...</div>
              </div>
            </div>
          ))}

          {logs.length > 3 && (
            <div
              style={{
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '0.75rem',
                padding: '8px',
              }}
            >
              ... and {logs.length - 3} more attestations
            </div>
          )}
        </div>

        {/* Daily Logs */}
        <h3 className="section-title">Daily Logs</h3>

        {logs.length === 0 ? (
          <div className="card" style={{ textAlign: 'center' }}>
            <p style={{ color: 'var(--text-secondary)' }}>
              No logs yet. Add your first daily log!
            </p>
          </div>
        ) : (
          [...logs].reverse().map((log) => (
            <div key={log.id} className="log-entry">
              <div className="log-header">
                <span className="log-date">
                  {format(new Date(log.created_at), 'MMM d, yyyy • h:mm a')}
                </span>
                <span className="log-mood">{getMoodEmoji(log.mood)}</span>
              </div>

              <p className="log-note">{log.note}</p>

              <div className="log-footer">
                <div className="log-progress">
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Progress:
                  </span>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${log.progress_rating * 10}%` }}
                    ></div>
                  </div>
                  <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                    {log.progress_rating}/10
                  </span>
                </div>
                <span className="log-hash">#{log.hash.slice(0, 8)}</span>
              </div>
            </div>
          ))
        )}
      </div>

      <button className="fab" onClick={() => navigate(`/resolution/${id}/log`)}>
        +
      </button>

      <nav className="tab-bar">
        <button
          className="tab-item"
          onClick={() => navigate('/')}
          style={{ background: 'none', border: 'none' }}
        >
          <span className="tab-icon">🏠</span>
          <span className="tab-label">Home</span>
        </button>
        <button
          className="tab-item"
          onClick={() => navigate('/today')}
          style={{ background: 'none', border: 'none' }}
        >
          <span className="tab-icon">📅</span>
          <span className="tab-label">Today</span>
        </button>
      </nav>
    </div>
  );
}

export default ResolutionDetail;
