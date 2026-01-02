# Resolution Tracker iOS

A Tauri-based iOS app for tracking New Year's resolutions with NFT-like cryptographic attestation. Each resolution and daily log is cryptographically hashed and chained, creating an immutable record of your journey.

## Features

- **NFT-like Attestation**: Each resolution receives a unique cryptographic hash (Genesis Hash), and every daily log is chained to the previous entry using SHA-256.
- **Chain Verification**: Verify the integrity of your entire resolution journey at any time.
- **Daily Logging**: Track your progress with mood, ratings, and notes.
- **Streak Tracking**: See your current and longest streaks for each resolution.
- **Categories**: Organize resolutions by Health, Career, Financial, Personal Growth, and more.
- **Local-First**: All data stored securely on your device using SQLite.

## Architecture

### Cryptographic Attestation Chain

```
Resolution (Genesis)
    │
    ├── genesis_hash = SHA256(salt + id + title + description + category + created_at)
    │
    ▼
Daily Log #1
    │
    ├── previous_hash = genesis_hash
    ├── hash = SHA256(salt + id + resolution_id + date + note + rating + mood + previous_hash)
    │
    ▼
Daily Log #2
    │
    ├── previous_hash = log_1.hash
    ├── hash = SHA256(...)
    │
    ▼
    ...
```

This creates a tamper-evident chain similar to blockchain technology, ensuring your progress history cannot be altered.

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Backend**: Rust (Tauri 2.0)
- **Database**: SQLite (via rusqlite)
- **State Management**: Zustand
- **Styling**: Custom CSS with iOS-optimized design
- **Cryptography**: SHA-256 (sha2 crate)

## Prerequisites

- Node.js 18+
- Rust 1.70+
- Xcode 15+ (for iOS development)
- iOS Simulator or physical device

## Getting Started

### Install Dependencies

```bash
cd resolution-tracker-ios
npm install
```

### Development (Desktop)

```bash
npm run tauri:dev
```

### iOS Development

1. Initialize iOS project:
```bash
npm run tauri ios init
```

2. Run on iOS Simulator:
```bash
npm run tauri:ios:dev
```

3. Build for iOS:
```bash
npm run tauri:ios:build
```

## Project Structure

```
resolution-tracker-ios/
├── src/                    # React frontend
│   ├── components/         # UI components
│   ├── store/              # Zustand state management
│   ├── types/              # TypeScript types
│   ├── utils/              # Helper functions
│   ├── App.tsx             # Main app component
│   ├── main.tsx            # Entry point
│   └── styles.css          # Global styles
├── src-tauri/              # Rust backend
│   ├── src/
│   │   ├── main.rs         # Tauri commands
│   │   ├── models.rs       # Data models
│   │   ├── attestation.rs  # Cryptographic attestation
│   │   └── database.rs     # SQLite operations
│   ├── Cargo.toml          # Rust dependencies
│   └── tauri.conf.json     # Tauri configuration
└── package.json            # Node dependencies
```

## API Commands

The app exposes these Tauri commands:

| Command | Description |
|---------|-------------|
| `create_resolution` | Create a new resolution with genesis attestation |
| `get_all_resolutions` | Fetch all resolutions |
| `get_resolution` | Get a single resolution by ID |
| `add_daily_log` | Add a daily log entry (chained to previous) |
| `get_logs_for_resolution` | Get all logs for a resolution |
| `get_logs_for_date` | Get all logs for a specific date |
| `get_resolution_summary` | Get statistics for a resolution |
| `verify_chain_integrity` | Verify the attestation chain hasn't been tampered |
| `update_resolution_status` | Update resolution status (active/completed/paused) |
| `delete_resolution` | Delete a resolution and its logs |
| `get_streak` | Get the current streak for a resolution |

## Data Models

### Resolution
- `id`: Unique identifier (UUID v4)
- `title`: Resolution title
- `description`: Detailed description
- `category`: Category (Health, Career, etc.)
- `status`: active | completed | paused | abandoned
- `genesis_hash`: Initial cryptographic fingerprint
- `current_hash`: Head of the attestation chain
- `attestation_count`: Total entries in chain

### DailyLog
- `id`: Unique identifier (UUID v4)
- `resolution_id`: Parent resolution
- `date`: Log date (YYYY-MM-DD)
- `note`: Journal entry
- `progress_rating`: 1-10 scale
- `mood`: great | good | neutral | struggling | difficult
- `hash`: Cryptographic hash of this entry
- `previous_hash`: Hash of the previous entry in chain

## License

MIT
