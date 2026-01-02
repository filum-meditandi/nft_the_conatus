export interface Resolution {
  id: string;
  title: string;
  description: string;
  category: string;
  status: 'active' | 'completed' | 'paused' | 'abandoned';
  target_date: string | null;
  created_at: string;
  updated_at: string;
  genesis_hash: string;
  current_hash: string;
  attestation_count: number;
}

export interface DailyLog {
  id: string;
  resolution_id: string;
  date: string;
  note: string;
  progress_rating: number;
  mood: Mood;
  created_at: string;
  hash: string;
  previous_hash: string;
}

export type Mood = 'great' | 'good' | 'neutral' | 'struggling' | 'difficult';

export interface MoodDistribution {
  great: number;
  good: number;
  neutral: number;
  struggling: number;
  difficult: number;
}

export interface ResolutionSummary {
  resolution: Resolution;
  total_logs: number;
  average_progress: number;
  current_streak: number;
  longest_streak: number;
  mood_distribution: MoodDistribution;
  chain_verified: boolean;
  days_since_start: number;
  completion_percentage: number;
}

export const CATEGORIES = [
  'Health & Fitness',
  'Career & Education',
  'Financial',
  'Personal Growth',
  'Relationships',
  'Creativity',
  'Habits',
  'Other',
] as const;

export const MOODS: { value: Mood; emoji: string; label: string }[] = [
  { value: 'great', emoji: '🌟', label: 'Great' },
  { value: 'good', emoji: '😊', label: 'Good' },
  { value: 'neutral', emoji: '😐', label: 'Neutral' },
  { value: 'struggling', emoji: '😓', label: 'Struggling' },
  { value: 'difficult', emoji: '😔', label: 'Difficult' },
];
