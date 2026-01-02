// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod attestation;
mod database;
mod models;

use attestation::AttestationService;
use database::Database;
use models::{DailyLog, Resolution, ResolutionSummary};
use std::sync::Mutex;
use tauri::State;

struct AppState {
    db: Mutex<Database>,
    attestation: AttestationService,
}

#[tauri::command]
async fn create_resolution(
    state: State<'_, AppState>,
    title: String,
    description: String,
    category: String,
    target_date: Option<String>,
) -> Result<Resolution, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let resolution = Resolution::new(title, description, category, target_date);
    let attested = state.attestation.attest_resolution(&resolution);

    db.insert_resolution(&attested).map_err(|e| e.to_string())?;

    Ok(attested)
}

#[tauri::command]
async fn get_all_resolutions(state: State<'_, AppState>) -> Result<Vec<Resolution>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.get_all_resolutions().map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_resolution(state: State<'_, AppState>, id: String) -> Result<Resolution, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.get_resolution(&id).map_err(|e| e.to_string())
}

#[tauri::command]
async fn add_daily_log(
    state: State<'_, AppState>,
    resolution_id: String,
    note: String,
    progress_rating: i32,
    mood: String,
) -> Result<DailyLog, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    // Get the resolution to chain the attestation
    let resolution = db.get_resolution(&resolution_id).map_err(|e| e.to_string())?;

    let log = DailyLog::new(resolution_id, note, progress_rating, mood);
    let attested = state.attestation.attest_daily_log(&log, &resolution.current_hash);

    db.insert_daily_log(&attested).map_err(|e| e.to_string())?;

    // Update resolution's current hash for chain continuity
    db.update_resolution_hash(&attested.resolution_id, &attested.hash)
        .map_err(|e| e.to_string())?;

    Ok(attested)
}

#[tauri::command]
async fn get_logs_for_resolution(
    state: State<'_, AppState>,
    resolution_id: String,
) -> Result<Vec<DailyLog>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.get_logs_for_resolution(&resolution_id)
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_logs_for_date(
    state: State<'_, AppState>,
    date: String,
) -> Result<Vec<DailyLog>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.get_logs_for_date(&date).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_resolution_summary(
    state: State<'_, AppState>,
    resolution_id: String,
) -> Result<ResolutionSummary, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let resolution = db.get_resolution(&resolution_id).map_err(|e| e.to_string())?;
    let logs = db.get_logs_for_resolution(&resolution_id).map_err(|e| e.to_string())?;

    Ok(ResolutionSummary::from_resolution_and_logs(&resolution, &logs))
}

#[tauri::command]
async fn verify_chain_integrity(
    state: State<'_, AppState>,
    resolution_id: String,
) -> Result<bool, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let resolution = db.get_resolution(&resolution_id).map_err(|e| e.to_string())?;
    let logs = db.get_logs_for_resolution(&resolution_id).map_err(|e| e.to_string())?;

    Ok(state.attestation.verify_chain(&resolution, &logs))
}

#[tauri::command]
async fn update_resolution_status(
    state: State<'_, AppState>,
    resolution_id: String,
    status: String,
) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.update_resolution_status(&resolution_id, &status)
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn delete_resolution(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.delete_resolution(&id).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_streak(state: State<'_, AppState>, resolution_id: String) -> Result<i32, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.get_streak(&resolution_id).map_err(|e| e.to_string())
}

fn main() {
    let db = Database::new().expect("Failed to initialize database");
    db.initialize_tables().expect("Failed to create tables");

    let app_state = AppState {
        db: Mutex::new(db),
        attestation: AttestationService::new(),
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_sql::Builder::new().build())
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            create_resolution,
            get_all_resolutions,
            get_resolution,
            add_daily_log,
            get_logs_for_resolution,
            get_logs_for_date,
            get_resolution_summary,
            verify_chain_integrity,
            update_resolution_status,
            delete_resolution,
            get_streak,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
