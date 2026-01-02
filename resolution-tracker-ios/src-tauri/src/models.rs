use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Resolution {
    pub id: String,
    pub title: String,
    pub description: String,
    pub category: String,
    pub status: String,
    pub target_date: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    /// The genesis hash - initial cryptographic fingerprint
    pub genesis_hash: String,
    /// Current head of the attestation chain
    pub current_hash: String,
    /// Total number of attestations in the chain
    pub attestation_count: i32,
}

impl Resolution {
    pub fn new(
        title: String,
        description: String,
        category: String,
        target_date: Option<String>,
    ) -> Self {
        let now = Utc::now().to_rfc3339();
        let id = Uuid::new_v4().to_string();

        Resolution {
            id,
            title,
            description,
            category,
            status: "active".to_string(),
            target_date,
            created_at: now.clone(),
            updated_at: now,
            genesis_hash: String::new(),
            current_hash: String::new(),
            attestation_count: 0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DailyLog {
    pub id: String,
    pub resolution_id: String,
    pub date: String,
    pub note: String,
    pub progress_rating: i32,
    pub mood: String,
    pub created_at: String,
    /// Hash of this log entry
    pub hash: String,
    /// Hash of the previous entry in the chain
    pub previous_hash: String,
}

impl DailyLog {
    pub fn new(resolution_id: String, note: String, progress_rating: i32, mood: String) -> Self {
        let now = Utc::now();
        let id = Uuid::new_v4().to_string();

        DailyLog {
            id,
            resolution_id,
            date: now.format("%Y-%m-%d").to_string(),
            note,
            progress_rating: progress_rating.clamp(1, 10),
            mood,
            created_at: now.to_rfc3339(),
            hash: String::new(),
            previous_hash: String::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResolutionSummary {
    pub resolution: Resolution,
    pub total_logs: i32,
    pub average_progress: f64,
    pub current_streak: i32,
    pub longest_streak: i32,
    pub mood_distribution: MoodDistribution,
    pub chain_verified: bool,
    pub days_since_start: i32,
    pub completion_percentage: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MoodDistribution {
    pub great: i32,
    pub good: i32,
    pub neutral: i32,
    pub struggling: i32,
    pub difficult: i32,
}

impl MoodDistribution {
    pub fn new() -> Self {
        MoodDistribution {
            great: 0,
            good: 0,
            neutral: 0,
            struggling: 0,
            difficult: 0,
        }
    }

    pub fn add(&mut self, mood: &str) {
        match mood.to_lowercase().as_str() {
            "great" => self.great += 1,
            "good" => self.good += 1,
            "neutral" => self.neutral += 1,
            "struggling" => self.struggling += 1,
            "difficult" => self.difficult += 1,
            _ => self.neutral += 1,
        }
    }
}

impl ResolutionSummary {
    pub fn from_resolution_and_logs(resolution: &Resolution, logs: &[DailyLog]) -> Self {
        let total_logs = logs.len() as i32;

        let average_progress = if total_logs > 0 {
            logs.iter().map(|l| l.progress_rating as f64).sum::<f64>() / total_logs as f64
        } else {
            0.0
        };

        let mut mood_dist = MoodDistribution::new();
        for log in logs {
            mood_dist.add(&log.mood);
        }

        // Calculate streaks
        let (current_streak, longest_streak) = Self::calculate_streaks(logs);

        // Days since start
        let days_since_start = if let Ok(created) = DateTime::parse_from_rfc3339(&resolution.created_at) {
            (Utc::now() - created.with_timezone(&Utc)).num_days() as i32
        } else {
            0
        };

        // Completion percentage based on logs vs days
        let completion_percentage = if days_since_start > 0 {
            ((total_logs as f64 / days_since_start as f64) * 100.0).min(100.0)
        } else {
            0.0
        };

        ResolutionSummary {
            resolution: resolution.clone(),
            total_logs,
            average_progress,
            current_streak,
            longest_streak,
            mood_distribution: mood_dist,
            chain_verified: true,
            days_since_start,
            completion_percentage,
        }
    }

    fn calculate_streaks(logs: &[DailyLog]) -> (i32, i32) {
        if logs.is_empty() {
            return (0, 0);
        }

        let mut dates: Vec<String> = logs.iter().map(|l| l.date.clone()).collect();
        dates.sort();
        dates.dedup();

        let mut current_streak = 1;
        let mut longest_streak = 1;
        let mut streak = 1;

        for i in 1..dates.len() {
            let prev = chrono::NaiveDate::parse_from_str(&dates[i - 1], "%Y-%m-%d");
            let curr = chrono::NaiveDate::parse_from_str(&dates[i], "%Y-%m-%d");

            if let (Ok(p), Ok(c)) = (prev, curr) {
                if (c - p).num_days() == 1 {
                    streak += 1;
                    longest_streak = longest_streak.max(streak);
                } else {
                    streak = 1;
                }
            }
        }

        // Check if the most recent log is today or yesterday for current streak
        if let Some(last_date) = dates.last() {
            if let Ok(last) = chrono::NaiveDate::parse_from_str(last_date, "%Y-%m-%d") {
                let today = Utc::now().naive_utc().date();
                let diff = (today - last).num_days();
                if diff <= 1 {
                    current_streak = streak;
                } else {
                    current_streak = 0;
                }
            }
        }

        (current_streak, longest_streak)
    }
}
