use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RenderRequest {
    project_json: String,
    engine: Option<String>,
}

#[derive(Debug, Serialize)]
struct CommandOutput {
    stdout: String,
}

fn repo_root() -> Result<PathBuf, String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    if cwd.join("core/pipeline.py").exists() {
        return Ok(cwd);
    }
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    for ancestor in exe.ancestors() {
        if ancestor.join("core/pipeline.py").exists() {
            return Ok(ancestor.to_path_buf());
        }
        if ancestor.join("resources/core/pipeline.py").exists() {
            return Ok(ancestor.join("resources"));
        }
    }
    Err("Could not locate core/pipeline.py. Run from the project root or use a packaged build with resources.".to_string())
}

fn python_bin() -> String {
    std::env::var("PYTHON").unwrap_or_else(|_| "python3".to_string())
}

fn run_pipeline(args: &[String]) -> Result<CommandOutput, String> {
    let root = repo_root()?;
    let pipeline = root.join("core/pipeline.py");
    let output = Command::new(python_bin())
        .arg(pipeline)
        .args(args)
        .current_dir(&root)
        .output()
        .map_err(|e| format!("Failed to start Python pipeline: {e}"))?;
    if !output.status.success() {
        return Err(format!(
            "Pipeline failed with status {}\n{}",
            output.status,
            String::from_utf8_lossy(&output.stderr)
        ));
    }
    Ok(CommandOutput { stdout: String::from_utf8_lossy(&output.stdout).to_string() })
}

#[tauri::command]
fn generate_scenes(prompt: String, video_type: String, duration: u32, style: String, language: String, voice: Option<String>, generate_images: Option<bool>, image_engine: Option<String>) -> Result<String, String> {
    let mut args = vec![
        "plan".to_string(),
        "--prompt".to_string(), prompt,
        "--video-type".to_string(), video_type,
        "--duration".to_string(), duration.to_string(),
        "--style".to_string(), style,
        "--language".to_string(), language,
        "--save".to_string(),
    ];
    if let Some(voice) = voice.filter(|v| !v.trim().is_empty()) {
        args.push("--voice".to_string());
        args.push(voice);
    }
    if generate_images.unwrap_or(false) {
        args.push("--generate-images".to_string());
    }
    if let Some(engine) = image_engine.filter(|v| !v.trim().is_empty()) {
        args.push("--image-engine".to_string());
        args.push(engine);
    }
    run_pipeline(&args).map(|o| o.stdout)
}

#[tauri::command]
fn ai_status() -> Result<String, String> {
    let args = vec!["status".to_string()];
    run_pipeline(&args).map(|o| o.stdout)
}

#[tauri::command]
fn image_engines_status() -> Result<String, String> {
    let args = vec!["status".to_string()];
    run_pipeline(&args).map(|o| o.stdout)
}

#[tauri::command]
fn render_video(request: RenderRequest) -> Result<String, String> {
    let root = repo_root()?;
    let projects = root.join("storage/projects");
    fs::create_dir_all(&projects).map_err(|e| e.to_string())?;
    let now = SystemTime::now().duration_since(UNIX_EPOCH).map_err(|e| e.to_string())?.as_secs();
    let project_path = projects.join(format!("ui-project-{now}.json"));
    fs::write(&project_path, request.project_json).map_err(|e| e.to_string())?;
    let args = vec!["render".to_string(), "--project".to_string(), display_path(&project_path)];
    run_pipeline(&args).map(|o| o.stdout)
}

#[tauri::command]
fn generate_images(request: RenderRequest) -> Result<String, String> {
    let root = repo_root()?;
    let projects = root.join("storage/projects");
    fs::create_dir_all(&projects).map_err(|e| e.to_string())?;
    let now = SystemTime::now().duration_since(UNIX_EPOCH).map_err(|e| e.to_string())?.as_secs();
    let project_path = projects.join(format!("ui-image-project-{now}.json"));
    fs::write(&project_path, request.project_json).map_err(|e| e.to_string())?;
    let mut args = vec!["images".to_string(), "--project".to_string(), display_path(&project_path)];
    if let Some(engine) = request.engine.filter(|v| !v.trim().is_empty()) {
        args.push("--engine".to_string());
        args.push(engine);
    }
    run_pipeline(&args).map(|o| o.stdout)
}

#[tauri::command]
fn reveal_path(path: String) -> Result<(), String> {
    tauri_plugin_opener::open_path(path, None::<String>).map_err(|e| e.to_string())
}

fn display_path(path: &Path) -> String {
    path.to_string_lossy().to_string()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![ai_status, image_engines_status, generate_scenes, generate_images, render_video, reveal_path])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
