// app commands are declared so that a capability can expose some of them to the UI served
// by the backend (remote origin): see capabilities/backend-ui.json
const COMMANDS: &[&str] = &[
    "check_status",
    "check_update",
    "install_uv",
    "create_venv",
    "install_panoptic",
    "update_panoptic",
    "list_versions",
    "install_versions",
    "launch_backend",
    "stop_backend",
    "set_install_dir",
    "set_skip_dev_updates",
    "switch_db",
    "open_backend_ui",
    "show_launcher",
    "frontend_log",
];

fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(COMMANDS)),
    )
    .expect("failed to run tauri-build");
}
