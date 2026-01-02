import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import type { Resolution, DailyLog, ResolutionSummary, Mood } from '../types';

interface ResolutionState {
  resolutions: Resolution[];
  currentResolution: Resolution | null;
  logs: DailyLog[];
  summary: ResolutionSummary | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchResolutions: () => Promise<void>;
  createResolution: (
    title: string,
    description: string,
    category: string,
    targetDate?: string
  ) => Promise<Resolution>;
  selectResolution: (id: string) => Promise<void>;
  addDailyLog: (
    resolutionId: string,
    note: string,
    progressRating: number,
    mood: Mood
  ) => Promise<DailyLog>;
  fetchLogsForResolution: (resolutionId: string) => Promise<void>;
  fetchLogsForDate: (date: string) => Promise<DailyLog[]>;
  fetchSummary: (resolutionId: string) => Promise<void>;
  verifyChain: (resolutionId: string) => Promise<boolean>;
  updateStatus: (resolutionId: string, status: string) => Promise<void>;
  deleteResolution: (id: string) => Promise<void>;
  getStreak: (resolutionId: string) => Promise<number>;
  clearError: () => void;
}

export const useResolutionStore = create<ResolutionState>((set, get) => ({
  resolutions: [],
  currentResolution: null,
  logs: [],
  summary: null,
  isLoading: false,
  error: null,

  fetchResolutions: async () => {
    set({ isLoading: true, error: null });
    try {
      const resolutions = await invoke<Resolution[]>('get_all_resolutions');
      set({ resolutions, isLoading: false });
    } catch (error) {
      set({ error: String(error), isLoading: false });
    }
  },

  createResolution: async (title, description, category, targetDate) => {
    set({ isLoading: true, error: null });
    try {
      const resolution = await invoke<Resolution>('create_resolution', {
        title,
        description,
        category,
        targetDate: targetDate || null,
      });
      set((state) => ({
        resolutions: [resolution, ...state.resolutions],
        isLoading: false,
      }));
      return resolution;
    } catch (error) {
      set({ error: String(error), isLoading: false });
      throw error;
    }
  },

  selectResolution: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const resolution = await invoke<Resolution>('get_resolution', { id });
      const logs = await invoke<DailyLog[]>('get_logs_for_resolution', {
        resolutionId: id,
      });
      const summary = await invoke<ResolutionSummary>('get_resolution_summary', {
        resolutionId: id,
      });
      set({ currentResolution: resolution, logs, summary, isLoading: false });
    } catch (error) {
      set({ error: String(error), isLoading: false });
    }
  },

  addDailyLog: async (resolutionId, note, progressRating, mood) => {
    set({ isLoading: true, error: null });
    try {
      const log = await invoke<DailyLog>('add_daily_log', {
        resolutionId,
        note,
        progressRating,
        mood,
      });
      set((state) => ({
        logs: [...state.logs, log],
        isLoading: false,
      }));
      // Refresh summary after adding log
      await get().fetchSummary(resolutionId);
      return log;
    } catch (error) {
      set({ error: String(error), isLoading: false });
      throw error;
    }
  },

  fetchLogsForResolution: async (resolutionId) => {
    set({ isLoading: true, error: null });
    try {
      const logs = await invoke<DailyLog[]>('get_logs_for_resolution', {
        resolutionId,
      });
      set({ logs, isLoading: false });
    } catch (error) {
      set({ error: String(error), isLoading: false });
    }
  },

  fetchLogsForDate: async (date) => {
    try {
      const logs = await invoke<DailyLog[]>('get_logs_for_date', { date });
      return logs;
    } catch (error) {
      set({ error: String(error) });
      return [];
    }
  },

  fetchSummary: async (resolutionId) => {
    try {
      const summary = await invoke<ResolutionSummary>('get_resolution_summary', {
        resolutionId,
      });
      set({ summary });
    } catch (error) {
      set({ error: String(error) });
    }
  },

  verifyChain: async (resolutionId) => {
    try {
      const isValid = await invoke<boolean>('verify_chain_integrity', {
        resolutionId,
      });
      return isValid;
    } catch (error) {
      set({ error: String(error) });
      return false;
    }
  },

  updateStatus: async (resolutionId, status) => {
    set({ isLoading: true, error: null });
    try {
      await invoke('update_resolution_status', { resolutionId, status });
      set((state) => ({
        resolutions: state.resolutions.map((r) =>
          r.id === resolutionId ? { ...r, status: status as Resolution['status'] } : r
        ),
        currentResolution:
          state.currentResolution?.id === resolutionId
            ? { ...state.currentResolution, status: status as Resolution['status'] }
            : state.currentResolution,
        isLoading: false,
      }));
    } catch (error) {
      set({ error: String(error), isLoading: false });
    }
  },

  deleteResolution: async (id) => {
    set({ isLoading: true, error: null });
    try {
      await invoke('delete_resolution', { id });
      set((state) => ({
        resolutions: state.resolutions.filter((r) => r.id !== id),
        currentResolution:
          state.currentResolution?.id === id ? null : state.currentResolution,
        isLoading: false,
      }));
    } catch (error) {
      set({ error: String(error), isLoading: false });
    }
  },

  getStreak: async (resolutionId) => {
    try {
      const streak = await invoke<number>('get_streak', { resolutionId });
      return streak;
    } catch (error) {
      return 0;
    }
  },

  clearError: () => set({ error: null }),
}));
