use std::ffi::OsStr;

fn usage() -> &'static str {
    "usage: herdr-navigator <left|down|up|right> <alt-key>"
}

fn pane_id(herdr: &OsStr) -> Result<String, String> {
    if let Some(pane_id) = herdr_navigator::env_pane_id() {
        return Ok(pane_id);
    }

    let current = herdr_navigator::command_output(herdr, ["pane", "current"])?;
    herdr_navigator::current_pane_id(&current)
        .ok_or_else(|| "could not read current Herdr pane id".to_string())
}

fn foreground_process(herdr: &OsStr, pane_id: &str) -> Option<String> {
    herdr_navigator::command_output(herdr, ["pane", "process-info", "--pane", pane_id])
        .ok()
        .and_then(|json| herdr_navigator::foreground_process_name(&json))
}

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let direction = args.next().ok_or_else(|| usage().to_string())?;
    let key = args.next().ok_or_else(|| usage().to_string())?;

    if args.next().is_some() || !matches!(direction.as_str(), "left" | "down" | "up" | "right") {
        return Err(usage().to_string());
    }

    let herdr = herdr_navigator::herdr_binary();
    let pane_id = pane_id(herdr.as_os_str())?;
    let process_name = foreground_process(herdr.as_os_str(), &pane_id);
    let command =
        herdr_navigator::choose_command(&pane_id, process_name.as_deref(), &direction, &key);

    herdr_navigator::run_herdr(herdr.as_os_str(), command.args())
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}
