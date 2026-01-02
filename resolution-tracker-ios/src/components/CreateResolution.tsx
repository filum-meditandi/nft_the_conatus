import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useResolutionStore } from '../store/resolutionStore';
import { CATEGORIES } from '../types';

function CreateResolution() {
  const navigate = useNavigate();
  const { createResolution, isLoading } = useResolutionStore();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [targetDate, setTargetDate] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    try {
      const resolution = await createResolution(
        title.trim(),
        description.trim(),
        category,
        targetDate || undefined
      );
      navigate(`/resolution/${resolution.id}`);
    } catch (error) {
      console.error('Failed to create resolution:', error);
    }
  };

  return (
    <div>
      <header className="header">
        <button className="back-button" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1>New Resolution</h1>
        <div style={{ width: 60 }}></div>
      </header>

      <form className="page" onSubmit={handleSubmit}>
        <div className="card">
          <div className="form-group">
            <label className="form-label">Resolution Title</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., Exercise 30 minutes daily"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              placeholder="Describe your resolution and why it matters to you..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Category</label>
            <select
              className="form-select"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Target Date (Optional)</label>
            <input
              type="date"
              className="form-input"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
            />
          </div>
        </div>

        <div className="card" style={{ background: 'var(--surface-elevated)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '2rem' }}>🔐</span>
            <div>
              <h4 style={{ marginBottom: '4px' }}>NFT Attestation</h4>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Your resolution will receive a unique cryptographic hash, creating an
                immutable record of your commitment.
              </p>
            </div>
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Creating...' : 'Mint Resolution NFT'}
        </button>
      </form>
    </div>
  );
}

export default CreateResolution;
