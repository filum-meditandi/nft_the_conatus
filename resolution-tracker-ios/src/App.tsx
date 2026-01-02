import { Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import { useResolutionStore } from './store/resolutionStore';
import HomePage from './components/HomePage';
import ResolutionDetail from './components/ResolutionDetail';
import CreateResolution from './components/CreateResolution';
import DailyLogForm from './components/DailyLogForm';
import TodayView from './components/TodayView';

function App() {
  const fetchResolutions = useResolutionStore((state) => state.fetchResolutions);

  useEffect(() => {
    fetchResolutions();
  }, [fetchResolutions]);

  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/today" element={<TodayView />} />
        <Route path="/create" element={<CreateResolution />} />
        <Route path="/resolution/:id" element={<ResolutionDetail />} />
        <Route path="/resolution/:id/log" element={<DailyLogForm />} />
      </Routes>
    </div>
  );
}

export default App;
