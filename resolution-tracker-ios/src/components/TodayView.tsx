import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useResolutionStore } from '../store/resolutionStore';
import { format } from 'date-fns';
import type { DailyLog } from '../types';

function TodayView() {
  const navigate = useNavigate();
  const { resolutions, fetchLogsForDate, getStreak } = useResolutionStore();
  const [todayLogs, setTodayLogs] = useState<DailyLog[]>([]);
  const [streaks, setStreaks] = useState<Record<string, number>>({});

  const today = format(new Date(), 'yyyy-MM-dd');
  const displayDate = format(new Date(), 'EEEE, MMMM d');

  useEffect(() => {
    fetchLogsForDate(today).then(setTodayLogs);
  }, [today, fetchLogsForDate]);

  useEffect(() => {
    const loadStreaks = async () => {
      const streakMap: Record<string, number> = {};
      for (const res of resolutions) {
        streakMap[res.id] = await getStreak(res.id);
      }
      setStreaks(streakMap);
    };
    loadStreaks();
  }, [resolutions, getStreak]);

  const activeResolutions = resolutions.filter((r) => r.status === 'active');
  const loggedToday = new Set(todayLogs.map((l) => l.resolution_id));
  const pendingResolutions = activeResolutions.filter((r) => !loggedToday.has(r.id));
  const completedResolutions = activeResolutions.filter((r) => loggedToday.has(r.id));

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning!';
    if (hour < 17) return 'Good afternoon!';
    return 'Good evening!';
  };

  return (
    <div>
      <div className="today-header">
        <div className="today-date">{displayDate}</div>
        <h1 className="today-greeting">{getGreeting()}</h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>
          {pendingResolutions.length === 0
            ? 'All caught up!'
            : `${pendingResolutions.length} resolution${pendingResolutions.length === 1 ? '' : 's'} to log`}
        </p>
      </div>

      <div className="resolutions-to-log">
        {pendingResolutions.length > 0 && (
          <>
            <h3 className="section-title">Needs Logging</h3>
            {pendingResolutions.map((resolution) => (
              <div
                key={resolution.id}
                className="card resolution-card"
                onClick={() => navigate(`/resolution/${resolution.id}/log`)}
              >
                <div className="card-header">
                  <div>
                    <h3 className="card-title">{resolution.title}</h3>
                    <span className="resolution-category">{resolution.category}</span>
                  </div>
                  {streaks[resolution.id] > 0 && (
                    <div className="streak-badge">
                      🔥 {streaks[resolution.id]}
                    </div>
                  )}
                </div>
                <div
                  style={{
                    marginTop: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: 'var(--primary)',
                    fontSize: '0.875rem',
                  }}
                >
                  <span>Tap to add today's log</span>
                  <span>→</span>
                </div>
              </div>
            ))}
          </>
        )}

        {completedResolutions.length > 0 && (
          <>
            <h3 className="section-title" style={{ marginTop: '24px' }}>
              Logged Today
            </h3>
            {completedResolutions.map((resolution) => {
              const log = todayLogs.find((l) => l.resolution_id === resolution.id);
              return (
                <div
                  key={resolution.id}
                  className="card"
                  onClick={() => navigate(`/resolution/${resolution.id}`)}
                  style={{ cursor: 'pointer', opacity: 0.8 }}
                >
                  <div className="card-header">
                    <div>
                      <h3 className="card-title">{resolution.title}</h3>
                      <span className="resolution-category">{resolution.category}</span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '1.5rem' }}>✓</div>
                      {streaks[resolution.id] > 0 && (
                        <div className="streak-badge" style={{ marginTop: '8px' }}>
                          🔥 {streaks[resolution.id]}
                        </div>
                      )}
                    </div>
                  </div>
                  {log && (
                    <div
                      style={{
                        marginTop: '12px',
                        paddingTop: '12px',
                        borderTop: '1px solid var(--border)',
                      }}
                    >
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
                    </div>
                  )}
                </div>
              );
            })}
          </>
        )}

        {activeResolutions.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">🎯</div>
            <h2 className="empty-state-title">No Active Resolutions</h2>
            <p className="empty-state-text">
              Create a resolution to start tracking your daily progress.
            </p>
            <button className="btn btn-primary" onClick={() => navigate('/create')}>
              Create Resolution
            </button>
          </div>
        )}
      </div>

      <nav className="tab-bar">
        <Link to="/" className="tab-item">
          <span className="tab-icon">🏠</span>
          <span className="tab-label">Home</span>
        </Link>
        <Link to="/today" className="tab-item active">
          <span className="tab-icon">📅</span>
          <span className="tab-label">Today</span>
        </Link>
      </nav>
    </div>
  );
}

export default TodayView;
