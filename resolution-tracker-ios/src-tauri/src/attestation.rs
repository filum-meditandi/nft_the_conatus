use crate::models::{DailyLog, Resolution};
use sha2::{Digest, Sha256};

/// NFT-like attestation service that creates cryptographic proofs
/// for resolutions and their daily logs, forming an immutable chain.
pub struct AttestationService {
    /// Application-level salt for hashing
    salt: String,
}

impl AttestationService {
    pub fn new() -> Self {
        AttestationService {
            salt: "resolution-tracker-v1".to_string(),
        }
    }

    /// Creates the genesis attestation for a new resolution
    pub fn attest_resolution(&self, resolution: &Resolution) -> Resolution {
        let mut attested = resolution.clone();

        // Create the genesis hash from resolution data
        let genesis_data = format!(
            "{}:{}:{}:{}:{}:{}",
            self.salt,
            resolution.id,
            resolution.title,
            resolution.description,
            resolution.category,
            resolution.created_at
        );

        let genesis_hash = self.compute_hash(&genesis_data);

        attested.genesis_hash = genesis_hash.clone();
        attested.current_hash = genesis_hash;
        attested.attestation_count = 1;

        attested
    }

    /// Creates an attestation for a daily log, chaining it to the previous hash
    pub fn attest_daily_log(&self, log: &DailyLog, previous_hash: &str) -> DailyLog {
        let mut attested = log.clone();

        // Chain to previous hash (like blockchain)
        attested.previous_hash = previous_hash.to_string();

        // Create hash from log data + previous hash
        let log_data = format!(
            "{}:{}:{}:{}:{}:{}:{}:{}",
            self.salt,
            log.id,
            log.resolution_id,
            log.date,
            log.note,
            log.progress_rating,
            log.mood,
            previous_hash
        );

        attested.hash = self.compute_hash(&log_data);

        attested
    }

    /// Verifies the integrity of the entire attestation chain
    pub fn verify_chain(&self, resolution: &Resolution, logs: &[DailyLog]) -> bool {
        if logs.is_empty() {
            return true;
        }

        // Verify first log chains from genesis
        let first_log = &logs[0];
        if first_log.previous_hash != resolution.genesis_hash {
            return false;
        }

        // Verify each log's hash is correctly computed
        for (i, log) in logs.iter().enumerate() {
            let expected_previous = if i == 0 {
                &resolution.genesis_hash
            } else {
                &logs[i - 1].hash
            };

            if &log.previous_hash != expected_previous {
                return false;
            }

            // Recompute and verify hash
            let log_data = format!(
                "{}:{}:{}:{}:{}:{}:{}:{}",
                self.salt,
                log.id,
                log.resolution_id,
                log.date,
                log.note,
                log.progress_rating,
                log.mood,
                log.previous_hash
            );

            let computed_hash = self.compute_hash(&log_data);
            if computed_hash != log.hash {
                return false;
            }
        }

        // Verify the resolution's current hash matches the last log
        if let Some(last_log) = logs.last() {
            if resolution.current_hash != last_log.hash {
                return false;
            }
        }

        true
    }

    /// Computes SHA-256 hash and returns hex string
    fn compute_hash(&self, data: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        let result = hasher.finalize();
        hex::encode(result)
    }

    /// Generates a short display hash (first 8 chars)
    pub fn short_hash(hash: &str) -> String {
        hash.chars().take(8).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolution_attestation() {
        let service = AttestationService::new();
        let resolution = Resolution::new(
            "Exercise Daily".to_string(),
            "30 minutes of exercise every day".to_string(),
            "Health".to_string(),
            None,
        );

        let attested = service.attest_resolution(&resolution);

        assert!(!attested.genesis_hash.is_empty());
        assert_eq!(attested.genesis_hash, attested.current_hash);
        assert_eq!(attested.attestation_count, 1);
    }

    #[test]
    fn test_log_chain() {
        let service = AttestationService::new();
        let resolution = Resolution::new(
            "Read More".to_string(),
            "Read 1 book per month".to_string(),
            "Personal Development".to_string(),
            None,
        );

        let attested_resolution = service.attest_resolution(&resolution);

        let log1 = DailyLog::new(
            attested_resolution.id.clone(),
            "Read chapter 1".to_string(),
            7,
            "good".to_string(),
        );

        let attested_log1 = service.attest_daily_log(&log1, &attested_resolution.genesis_hash);

        assert_eq!(attested_log1.previous_hash, attested_resolution.genesis_hash);
        assert!(!attested_log1.hash.is_empty());

        let log2 = DailyLog::new(
            attested_resolution.id.clone(),
            "Read chapter 2".to_string(),
            8,
            "great".to_string(),
        );

        let attested_log2 = service.attest_daily_log(&log2, &attested_log1.hash);

        assert_eq!(attested_log2.previous_hash, attested_log1.hash);
    }
}
