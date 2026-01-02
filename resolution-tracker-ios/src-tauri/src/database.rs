use crate::models::{DailyLog, Resolution};
use rusqlite::{params, Connection, Result};
use std::path::PathBuf;

pub struct Database {
    conn: Connection,
}

impl Database {
    pub fn new() -> Result<Self> {
        let db_path = Self::get_db_path();

        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent).ok();
        }

        let conn = Connection::open(&db_path)?;
        Ok(Database { conn })
    }

    fn get_db_path() -> PathBuf {
        #[cfg(target_os = "ios")]
        {
            // iOS uses the app's Documents directory
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(home)
                .join("Documents")
                .join("resolutions.db")
        }

        #[cfg(not(target_os = "ios"))]
        {
            // Desktop/development uses local directory
            let data_dir = dirs::data_local_dir()
                .unwrap_or_else(|| PathBuf::from("."))
                .join("resolution-tracker");
            data_dir.join("resolutions.db")
        }
    }

    pub fn initialize_tables(&self) -> Result<()> {
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS resolutions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                target_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                genesis_hash TEXT NOT NULL,
                current_hash TEXT NOT NULL,
                attestation_count INTEGER NOT NULL DEFAULT 1
            )",
            [],
        )?;

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS daily_logs (
                id TEXT PRIMARY KEY,
                resolution_id TEXT NOT NULL,
                date TEXT NOT NULL,
                note TEXT NOT NULL,
                progress_rating INTEGER NOT NULL,
                mood TEXT NOT NULL,
                created_at TEXT NOT NULL,
                hash TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                FOREIGN KEY (resolution_id) REFERENCES resolutions(id) ON DELETE CASCADE
            )",
            [],
        )?;

        // Index for faster queries
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_resolution_id ON daily_logs(resolution_id)",
            [],
        )?;

        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_date ON daily_logs(date)",
            [],
        )?;

        Ok(())
    }

    pub fn insert_resolution(&self, resolution: &Resolution) -> Result<()> {
        self.conn.execute(
            "INSERT INTO resolutions (
                id, title, description, category, status, target_date,
                created_at, updated_at, genesis_hash, current_hash, attestation_count
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
            params![
                resolution.id,
                resolution.title,
                resolution.description,
                resolution.category,
                resolution.status,
                resolution.target_date,
                resolution.created_at,
                resolution.updated_at,
                resolution.genesis_hash,
                resolution.current_hash,
                resolution.attestation_count,
            ],
        )?;
        Ok(())
    }

    pub fn get_all_resolutions(&self) -> Result<Vec<Resolution>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, title, description, category, status, target_date,
                    created_at, updated_at, genesis_hash, current_hash, attestation_count
             FROM resolutions ORDER BY created_at DESC",
        )?;

        let resolutions = stmt
            .query_map([], |row| {
                Ok(Resolution {
                    id: row.get(0)?,
                    title: row.get(1)?,
                    description: row.get(2)?,
                    category: row.get(3)?,
                    status: row.get(4)?,
                    target_date: row.get(5)?,
                    created_at: row.get(6)?,
                    updated_at: row.get(7)?,
                    genesis_hash: row.get(8)?,
                    current_hash: row.get(9)?,
                    attestation_count: row.get(10)?,
                })
            })?
            .collect::<Result<Vec<_>>>()?;

        Ok(resolutions)
    }

    pub fn get_resolution(&self, id: &str) -> Result<Resolution> {
        self.conn.query_row(
            "SELECT id, title, description, category, status, target_date,
                    created_at, updated_at, genesis_hash, current_hash, attestation_count
             FROM resolutions WHERE id = ?1",
            params![id],
            |row| {
                Ok(Resolution {
                    id: row.get(0)?,
                    title: row.get(1)?,
                    description: row.get(2)?,
                    category: row.get(3)?,
                    status: row.get(4)?,
                    target_date: row.get(5)?,
                    created_at: row.get(6)?,
                    updated_at: row.get(7)?,
                    genesis_hash: row.get(8)?,
                    current_hash: row.get(9)?,
                    attestation_count: row.get(10)?,
                })
            },
        )
    }

    pub fn update_resolution_hash(&self, id: &str, new_hash: &str) -> Result<()> {
        self.conn.execute(
            "UPDATE resolutions SET current_hash = ?1, attestation_count = attestation_count + 1,
             updated_at = datetime('now') WHERE id = ?2",
            params![new_hash, id],
        )?;
        Ok(())
    }

    pub fn update_resolution_status(&self, id: &str, status: &str) -> Result<()> {
        self.conn.execute(
            "UPDATE resolutions SET status = ?1, updated_at = datetime('now') WHERE id = ?2",
            params![status, id],
        )?;
        Ok(())
    }

    pub fn delete_resolution(&self, id: &str) -> Result<()> {
        self.conn.execute("DELETE FROM daily_logs WHERE resolution_id = ?1", params![id])?;
        self.conn.execute("DELETE FROM resolutions WHERE id = ?1", params![id])?;
        Ok(())
    }

    pub fn insert_daily_log(&self, log: &DailyLog) -> Result<()> {
        self.conn.execute(
            "INSERT INTO daily_logs (
                id, resolution_id, date, note, progress_rating, mood,
                created_at, hash, previous_hash
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![
                log.id,
                log.resolution_id,
                log.date,
                log.note,
                log.progress_rating,
                log.mood,
                log.created_at,
                log.hash,
                log.previous_hash,
            ],
        )?;
        Ok(())
    }

    pub fn get_logs_for_resolution(&self, resolution_id: &str) -> Result<Vec<DailyLog>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, resolution_id, date, note, progress_rating, mood,
                    created_at, hash, previous_hash
             FROM daily_logs WHERE resolution_id = ?1 ORDER BY created_at ASC",
        )?;

        let logs = stmt
            .query_map(params![resolution_id], |row| {
                Ok(DailyLog {
                    id: row.get(0)?,
                    resolution_id: row.get(1)?,
                    date: row.get(2)?,
                    note: row.get(3)?,
                    progress_rating: row.get(4)?,
                    mood: row.get(5)?,
                    created_at: row.get(6)?,
                    hash: row.get(7)?,
                    previous_hash: row.get(8)?,
                })
            })?
            .collect::<Result<Vec<_>>>()?;

        Ok(logs)
    }

    pub fn get_logs_for_date(&self, date: &str) -> Result<Vec<DailyLog>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, resolution_id, date, note, progress_rating, mood,
                    created_at, hash, previous_hash
             FROM daily_logs WHERE date = ?1 ORDER BY created_at DESC",
        )?;

        let logs = stmt
            .query_map(params![date], |row| {
                Ok(DailyLog {
                    id: row.get(0)?,
                    resolution_id: row.get(1)?,
                    date: row.get(2)?,
                    note: row.get(3)?,
                    progress_rating: row.get(4)?,
                    mood: row.get(5)?,
                    created_at: row.get(6)?,
                    hash: row.get(7)?,
                    previous_hash: row.get(8)?,
                })
            })?
            .collect::<Result<Vec<_>>>()?;

        Ok(logs)
    }

    pub fn get_streak(&self, resolution_id: &str) -> Result<i32> {
        let mut stmt = self.conn.prepare(
            "SELECT DISTINCT date FROM daily_logs
             WHERE resolution_id = ?1 ORDER BY date DESC",
        )?;

        let dates: Vec<String> = stmt
            .query_map(params![resolution_id], |row| row.get(0))?
            .filter_map(|r| r.ok())
            .collect();

        if dates.is_empty() {
            return Ok(0);
        }

        let today = chrono::Utc::now().format("%Y-%m-%d").to_string();
        let yesterday = (chrono::Utc::now() - chrono::Duration::days(1))
            .format("%Y-%m-%d")
            .to_string();

        // Check if most recent log is today or yesterday
        if dates[0] != today && dates[0] != yesterday {
            return Ok(0);
        }

        let mut streak = 1;
        for i in 1..dates.len() {
            let prev = chrono::NaiveDate::parse_from_str(&dates[i - 1], "%Y-%m-%d");
            let curr = chrono::NaiveDate::parse_from_str(&dates[i], "%Y-%m-%d");

            if let (Ok(p), Ok(c)) = (prev, curr) {
                if (p - c).num_days() == 1 {
                    streak += 1;
                } else {
                    break;
                }
            }
        }

        Ok(streak)
    }
}
