import { useNavigate, Link } from 'react-router-dom';
import { useResolutionStore } from '../store/resolutionStore';
import { format } from 'date-fns';

function HomePage() {
  const navigate = useNavigate();
  const { resolutions, isLoading } = useResolutionStore();

  const shortHash = (hash: string) => hash.slice(0, 8) + '...' + hash.slice(-4);

  return (
    <div className="page-wrapper">
      <header className="header">
        <h1>Resolutions</h1>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          {resolutions.length} NFTs
        </span>
      </header>

      <div className="page" style={{ paddingBottom: '160px' }}>
        {isLoading ? (
          <div className="loading">
            <div className="spinner"></div>
          </div>
        ) : resolutions.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🎯</div>
            <h2 className="empty-state-title">No Resolutions Yet</h2>
            <p className="empty-state-text">
              Create your first resolution to start tracking your goals with
              cryptographic attestation.
            </p>
            <button className="btn btn-primary" onClick={() => navigate('/create')}>
              Create Resolution
            </button>
          </div>
        ) : (
          resolutions.map((resolution) => (
            <div
              key={resolution.id}
              className="card resolution-card"
              onClick={() => navigate(`/resolution/${resolution.id}`)}
            >
              <div className="card-header">
                <div>
                  <h3 className="card-title">{resolution.title}</h3>
                  <p className="card-subtitle">{resolution.description}</p>
                </div>
                <span className="resolution-category">{resolution.category}</span>
              </div>

              <div
                className={`status-indicator status-${resolution.status}`}
                style={{ marginBottom: '12px' }}
              >
                <span className="status-dot"></span>
                <span style={{ textTransform: 'capitalize' }}>{resolution.status}</span>
              </div>

              <div className="nft-badge">
                <span className="nft-badge-icon">🔗</span>
                <div>
                  <div className="nft-label">Genesis Hash</div>
                  <div className="nft-hash">{shortHash(resolution.genesis_hash)}</div>
                </div>
              </div>

              <div className="resolution-stats">
                <div className="stat">
                  <div className="stat-value">{resolution.attestation_count}</div>
                  <div className="stat-label">Attestations</div>
                </div>
                <div className="stat">
                  <div className="stat-value">
                    {format(new Date(resolution.created_at), 'MMM d')}
                  </div>
                  <div className="stat-label">Created</div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <button className="fab" onClick={() => navigate('/create')}>
        +
      </button>

      <nav className="tab-bar">
        <Link to="/" className="tab-item active">
          <span className="tab-icon">🏠</span>
          <span className="tab-label">Home</span>
        </Link>
        <Link to="/today" className="tab-item">
          <span className="tab-icon">📅</span>
          <span className="tab-label">Today</span>
        </Link>
      </nav>
    </div>
  );
}

export default HomePage;
