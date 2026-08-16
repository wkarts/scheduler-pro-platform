mod commands;

use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::app_bootstrap,
            commands::disabled_modules,
            commands::api_config
        ])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("erro ao executar Scheduler Pro Desktop");
}
