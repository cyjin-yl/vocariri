#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use tauri::Manager;

#[cfg(debug_assertions)]
#[tauri::command]
fn finish_test(app: tauri::AppHandle) -> Result<(), String> {
    if std::env::var("VOCARIRI_TEST_MODE").as_deref() != Ok("1") {
        return Err("Only available in an explicit test session".into());
    }
    app.get_webview_window("main")
        .ok_or("Test window not found")?
        .close()
        .map_err(|e| e.to_string())
}

fn main() {
    let builder = tauri::Builder::default()
        .setup(|app| {
            if std::env::var("VOCARIRI_TEST_MODE").as_deref() != Ok("1") {
                if let Some(window) = app.get_webview_window("main") {
                    window.show()?;
                }
            }
            Ok(())
        });
    #[cfg(debug_assertions)]
    let builder = builder.invoke_handler(tauri::generate_handler![finish_test]);
    builder.run(tauri::generate_context!())
        .expect("Vocariri failed to start");
}
