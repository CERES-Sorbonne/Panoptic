use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter, Manager};

const BACKEND_PORT: u16 = 8000;
const BACKEND_START_TIMEOUT: Duration = Duration::from_secs(120);

struct BackendProcess(Mutex<Option<Child>>);

#[derive(Clone, serde::Serialize)]
struct LogLine {
    line: String,
    stream: &'static str,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct SetupStatus {
    backend_running: bool,
    uv_installed: bool,
    venv_exists: bool,
    panoptic_installed: bool,
    installed_version: Option<String>,
    os: &'static str,
    log_path: Option<String>,
    install_dir: Option<String>,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct UpdateInfo {
    update_available: bool,
    installed_version: Option<String>,
    latest_version: Option<String>,
}

#[derive(serde::Deserialize)]
struct OutdatedEntry {
    name: String,
    version: String,
    latest_version: String,
}

fn home_dir() -> Result<PathBuf, String> {
    dirs::home_dir().ok_or_else(|| "could not resolve home directory".to_string())
}

/// File persisting the user's chosen install directory (e.g. ~/.config/panoptic/install_dir)
fn install_dir_config_path() -> Result<PathBuf, String> {
    let dir = dirs::config_dir().ok_or_else(|| "could not resolve config directory".to_string())?;
    Ok(dir.join("panoptic").join("install_dir"))
}

fn panoptic_dir() -> Result<PathBuf, String> {
    if let Ok(config) = install_dir_config_path() {
        if let Ok(content) = std::fs::read_to_string(&config) {
            let path = content.trim();
            if !path.is_empty() {
                return Ok(PathBuf::from(path));
            }
        }
    }
    Ok(home_dir()?.join("panoptic"))
}

fn venv_dir() -> Result<PathBuf, String> {
    Ok(panoptic_dir()?.join(".venv"))
}

fn local_bin() -> Result<PathBuf, String> {
    Ok(home_dir()?.join(".local").join("bin"))
}

/// Absolute path to uv if it exists in ~/.local/bin, otherwise rely on PATH.
fn uv_bin() -> PathBuf {
    let name = if cfg!(windows) { "uv.exe" } else { "uv" };
    if let Ok(bin) = local_bin() {
        let path = bin.join(name);
        if path.exists() {
            return path;
        }
    }
    PathBuf::from(name)
}

fn backend_log_path() -> Result<PathBuf, String> {
    Ok(panoptic_dir()?.join("panoptic.log"))
}

/// Fresh log file for this session; the previous one is kept as panoptic.log.old
fn create_backend_log_file() -> Result<std::fs::File, String> {
    let path = backend_log_path()?;
    if path.exists() {
        let _ = std::fs::rename(&path, path.with_extension("log.old"));
    }
    std::fs::File::create(&path).map_err(|e| format!("failed to create {}: {e}", path.display()))
}

fn panoptic_bin() -> Result<PathBuf, String> {
    let venv = venv_dir()?;
    let path = if cfg!(windows) {
        venv.join("Scripts").join("panoptic.exe")
    } else {
        venv.join("bin").join("panoptic")
    };
    Ok(path)
}

fn new_command(program: impl AsRef<std::ffi::OsStr>) -> Command {
    #[allow(unused_mut)]
    let mut cmd = Command::new(program);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd
}

/// uv may live in ~/.local/bin without being on PATH (fresh install).
fn prepend_local_bin(cmd: &mut Command) {
    let Ok(bin) = local_bin() else { return };
    let path = std::env::var_os("PATH").unwrap_or_default();
    let mut paths = vec![bin];
    paths.extend(std::env::split_paths(&path));
    if let Ok(new_path) = std::env::join_paths(paths) {
        cmd.env("PATH", new_path);
    }
}

/// Command `uv <args>` running in ~/panoptic (where the .venv lives).
fn uv_command(args: &[&str]) -> Result<Command, String> {
    let mut cmd = new_command(uv_bin());
    cmd.args(args).current_dir(panoptic_dir()?);
    prepend_local_bin(&mut cmd);
    Ok(cmd)
}

fn spawn_log_reader(
    app: AppHandle,
    event: &'static str,
    stream: &'static str,
    file: Option<std::sync::Arc<Mutex<std::fs::File>>>,
    reader: impl std::io::Read + Send + 'static,
) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        use std::io::Write;
        for line in BufReader::new(reader).lines().map_while(Result::ok) {
            if let Some(file) = &file {
                if let Ok(mut file) = file.lock() {
                    let _ = writeln!(file, "{line}");
                }
            }
            if event == "backend-log" {
                eprintln!("[backend] {line}");
            }
            let _ = app.emit(event, LogLine { line, stream });
        }
    })
}

/// Run a command to completion, streaming stdout/stderr lines to the frontend.
fn run_streamed(app: &AppHandle, mut cmd: Command, event: &'static str) -> Result<(), String> {
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = cmd
        .spawn()
        .map_err(|e| format!("failed to run {:?}: {e}", cmd.get_program()))?;
    let readers: Vec<_> = [
        child.stdout.take().map(|out| spawn_log_reader(app.clone(), event, "stdout", None, out)),
        child.stderr.take().map(|err| spawn_log_reader(app.clone(), event, "stderr", None, err)),
    ]
    .into_iter()
    .flatten()
    .collect();
    let status = child.wait().map_err(|e| e.to_string())?;
    for reader in readers {
        let _ = reader.join();
    }
    if status.success() {
        Ok(())
    } else {
        Err(format!("command exited with status {status}"))
    }
}

fn port_open(port: u16) -> bool {
    let addr = std::net::SocketAddr::from(([127, 0, 0, 1], port));
    std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(400)).is_ok()
}

fn uv_available() -> bool {
    uv_bin().is_absolute() || {
        let mut cmd = new_command("uv");
        prepend_local_bin(&mut cmd);
        cmd.arg("--version")
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
}

fn installed_panoptic_version() -> Option<String> {
    let output = uv_command(&["pip", "show", "panoptic"]).ok()?.output().ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8_lossy(&output.stdout)
        .lines()
        .find_map(|l| l.strip_prefix("Version:").map(|v| v.trim().to_string()))
}

#[tauri::command]
async fn check_status() -> Result<SetupStatus, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let venv_exists = venv_dir()?.is_dir();
        let installed_version = if venv_exists { installed_panoptic_version() } else { None };
        Ok(SetupStatus {
            backend_running: port_open(BACKEND_PORT),
            uv_installed: uv_available(),
            venv_exists,
            panoptic_installed: installed_version.is_some(),
            installed_version,
            os: std::env::consts::OS,
            log_path: backend_log_path().ok().map(|p| p.display().to_string()),
            install_dir: panoptic_dir().ok().map(|p| p.display().to_string()),
        })
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn check_update() -> Result<UpdateInfo, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let output = uv_command(&["pip", "list", "--outdated", "--format", "json"])?
            .output()
            .map_err(|e| e.to_string())?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Ok(entries) = serde_json::from_str::<Vec<OutdatedEntry>>(&stdout) {
            let panoptic = entries.into_iter().find(|e| e.name == "panoptic");
            return Ok(UpdateInfo {
                update_available: panoptic.is_some(),
                installed_version: panoptic.as_ref().map(|e| e.version.clone()),
                latest_version: panoptic.map(|e| e.latest_version),
            });
        }
        // fallback: same detection as the install scripts (plain text output)
        let output = uv_command(&["pip", "list", "--outdated"])?
            .output()
            .map_err(|e| e.to_string())?;
        Ok(UpdateInfo {
            update_available: String::from_utf8_lossy(&output.stdout).contains("panoptic"),
            installed_version: installed_panoptic_version(),
            latest_version: None,
        })
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn install_uv(app: AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut cmd = if cfg!(windows) {
            let mut cmd = new_command("powershell");
            cmd.args([
                "-ExecutionPolicy",
                "ByPass",
                "-c",
                "irm https://astral.sh/uv/install.ps1 | iex",
            ]);
            cmd
        } else {
            let mut cmd = new_command("sh");
            cmd.args(["-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]);
            cmd
        };
        cmd.current_dir(home_dir()?);
        run_streamed(&app, cmd, "install-log")?;
        if !uv_available() {
            return Err("uv was not found after installation".to_string());
        }
        Ok(())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn create_venv(app: AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        std::fs::create_dir_all(panoptic_dir()?).map_err(|e| e.to_string())?;
        if !venv_dir()?.exists() {
            run_streamed(&app, uv_command(&["venv", "--python", "3.12"])?, "install-log")?;
        }
        // like the install scripts, make sure pip exists in the venv on every launch
        run_streamed(&app, uv_command(&["pip", "install", "pip"])?, "install-log")
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn install_panoptic(app: AppHandle, gpu_mode: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        run_streamed(&app, uv_command(&["pip", "install", "panoptic"])?, "install-log")?;
        match gpu_mode.as_str() {
            "cuda" => run_streamed(
                &app,
                uv_command(&["pip", "install", "torch", "torchvision", "--torch-backend=auto"])?,
                "install-log",
            )?,
            "cpu" => run_streamed(
                &app,
                uv_command(&[
                    "pip",
                    "install",
                    "torch",
                    "torchvision",
                    "--index-url",
                    "https://download.pytorch.org/whl/cpu",
                ])?,
                "install-log",
            )?,
            // "default" (macOS): let panoptic pull the standard torch wheels
            _ => {}
        }
        let mut plugins = new_command(panoptic_bin()?);
        plugins.args(["plugins", "add", "vision"]).current_dir(panoptic_dir()?);
        run_streamed(&app, plugins, "install-log")
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn update_panoptic(app: AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        run_streamed(&app, uv_command(&["pip", "install", "-U", "panoptic"])?, "install-log")
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn launch_backend(app: AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        if port_open(BACKEND_PORT) {
            // already running (e.g. dev backend) — nothing to launch, nothing to kill later
            return Ok(());
        }
        let bin = panoptic_bin()?;
        if !bin.exists() {
            return Err(format!("panoptic executable not found at {}", bin.display()));
        }
        let mut cmd = new_command(&bin);
        cmd.env("PANOPTIC_REMOTE", "1")
            // released versions default to port 8000: pin the port the embedded UI is built for
            .env("PANOPTIC_PORT", BACKEND_PORT.to_string())
            .current_dir(panoptic_dir()?)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(target_os = "linux")]
        {
            use std::os::unix::process::CommandExt;
            // if the app dies without running the exit handler (crash, SIGKILL),
            // let the kernel kill the backend with it
            unsafe {
                cmd.pre_exec(|| {
                    libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL);
                    Ok(())
                });
            }
        }
        // PDEATHSIG fires when the spawning *thread* dies, so spawn from a dedicated
        // thread kept alive for the whole app lifetime (never from the ephemeral
        // tokio blocking pool, which would SIGKILL the backend seconds later)
        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            let spawned = cmd.spawn();
            let parent_must_stay = spawned.is_ok();
            let _ = tx.send(spawned);
            while parent_must_stay {
                std::thread::park();
            }
        });
        let mut child = rx
            .recv()
            .map_err(|e| e.to_string())?
            .map_err(|e| format!("failed to start backend: {e}"))?;
        let log_file = create_backend_log_file()
            .ok()
            .map(|f| std::sync::Arc::new(Mutex::new(f)));
        if let Some(out) = child.stdout.take() {
            spawn_log_reader(app.clone(), "backend-log", "stdout", log_file.clone(), out);
        }
        if let Some(err) = child.stderr.take() {
            spawn_log_reader(app.clone(), "backend-log", "stderr", log_file, err);
        }
        let state = app.state::<BackendProcess>();
        *state.0.lock().unwrap() = Some(child);

        let start = Instant::now();
        loop {
            if port_open(BACKEND_PORT) {
                return Ok(());
            }
            {
                let mut guard = state.0.lock().unwrap();
                if let Some(child) = guard.as_mut() {
                    if let Ok(Some(status)) = child.try_wait() {
                        guard.take();
                        return Err(format!("backend exited early with status {status}"));
                    }
                }
            }
            if start.elapsed() > BACKEND_START_TIMEOUT {
                // leave the child running: logs stay visible and a retry re-checks the port
                return Err(format!(
                    "backend did not answer on port {BACKEND_PORT} within {}s",
                    BACKEND_START_TIMEOUT.as_secs()
                ));
            }
            std::thread::sleep(Duration::from_millis(500));
        }
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn set_install_dir(path: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let dir = PathBuf::from(path.trim());
        if !dir.is_absolute() {
            return Err("install directory must be an absolute path".to_string());
        }
        std::fs::create_dir_all(&dir)
            .map_err(|e| format!("cannot create {}: {e}", dir.display()))?;
        let config = install_dir_config_path()?;
        if let Some(parent) = config.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        std::fs::write(&config, dir.to_string_lossy().as_bytes()).map_err(|e| e.to_string())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
fn frontend_log(message: String) {
    eprintln!("[webview] {message}");
}

#[tauri::command]
async fn stop_backend(app: AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        kill_backend(&app);
        Ok(())
    })
    .await
    .map_err(|e| e.to_string())?
}

fn kill_backend(app: &AppHandle) {
    // only kills a backend we spawned ourselves (state is None otherwise)
    // NOTE Windows contingency: if orphaned python children ever survive this,
    // switch to `taskkill /PID <pid> /T /F` to kill the whole tree.
    if let Some(state) = app.try_state::<BackendProcess>() {
        if let Some(mut child) = state.0.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(BackendProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            check_status,
            check_update,
            install_uv,
            create_venv,
            install_panoptic,
            update_panoptic,
            launch_backend,
            stop_backend,
            set_install_dir,
            frontend_log
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if matches!(
                event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                kill_backend(app_handle);
            }
        });
}
