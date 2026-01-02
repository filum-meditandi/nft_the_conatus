import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useResolutionStore } from '../store/resolutionStore';
import { MOODS, Mood } from '../types';

function DailyLogForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentResolution, selectResolution, addDailyLog, isLoading } =
    useResolutionStore();

  const [note, setNote] = useState('');
  const [progressRating, setProgressRating] = useState(5);
  const [mood, setMood] = useState<Mood>('neutral');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (id && !currentResolution) {
      selectResolution(id);
    }
  }, [id, currentResolution, selectResolution]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !note.trim()) return;

    try {
      await addDailyLog(id, note.trim(), progressRating, mood);
      setSuccess(true);
      setTimeout(() => {
        navigate(`/resolution/${id}`);
      }, 1500);
    } catch (error) {
      console.error('Failed to add log:', error);
    }
  };

  if (success) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          padding: '20px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: '4rem', marginBottom: '20px' }}>✓</div>
        <h2 style={{ marginBottom: '8px' }}>Log Attested!</h2>
        <p style={{ color: 'var(--text-secondary)' }}>
          Your daily log has been cryptographically chained.
        </p>
      </div>
    );
  }

  return (
    <div>
      <header className="header">
        <button className="back-button" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1>Daily Log</h1>
        <div style={{ width: 60 }}></div>
      </header>

      <form className="page" onSubmit={handleSubmit}>
        {currentResolution && (
          <div
            className="card"
            style={{ background: 'var(--surface-elevated)', marginBottom: '20px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '1.5rem' }}>🎯</span>
              <div>
                <h4>{currentResolution.title}</h4>
                <p
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)',
                    fontFamily: 'monospace',
                  }}
                >
                  Chain: #{currentResolution.current_hash.slice(0, 8)}...
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="card">
          <div className="form-group">
            <label className="form-label">How are you feeling?</label>
            <div className="mood-selector">
              {MOODS.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  className={`mood-option ${mood === m.value ? 'selected' : ''}`}
                  onClick={() => setMood(m.value)}
                >
                  <span className="mood-emoji">{m.emoji}</span>
                  <span className="mood-label">{m.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              Progress Rating: <strong>{progressRating}/10</strong>
            </label>
            <div className="progress-rating">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => (
                <button
                  key={num}
                  type="button"
                  className={`rating-dot ${
                    num === progressRating
                      ? 'selected'
                      : num < progressRating
                        ? 'filled'
                        : ''
                  }`}
                  onClick={() => setProgressRating(num)}
                >
                  {num}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">What did you accomplish today?</label>
            <textarea
              className="form-textarea"
              placeholder="Describe your progress, challenges, or thoughts..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="card" style={{ background: 'var(--surface-elevated)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '2rem' }}>🔐</span>
            <div>
              <h4 style={{ marginBottom: '4px' }}>Attestation</h4>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                This log will be cryptographically linked to your previous entries,
                creating an immutable chain of your journey.
              </p>
            </div>
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Attesting...' : 'Add to Chain'}
        </button>
      </form>
    </div>
  );
}

export default DailyLogForm;
