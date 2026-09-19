use std::ffi::{OsStr, OsString};
use std::process::Command;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NavigatorCommand {
    SendKeys { pane_id: String, key: String },
    Focus { pane_id: String, direction: String },
}

impl NavigatorCommand {
    pub fn args(&self) -> Vec<String> {
        match self {
            NavigatorCommand::SendKeys { pane_id, key } => {
                vec![
                    "pane".into(),
                    "send-keys".into(),
                    pane_id.clone(),
                    key.clone(),
                ]
            }
            NavigatorCommand::Focus { pane_id, direction } => vec![
                "pane".into(),
                "focus".into(),
                "--direction".into(),
                direction.clone(),
                "--pane".into(),
                pane_id.clone(),
            ],
        }
    }
}

pub fn is_vim_process(process_name: &str) -> bool {
    matches!(process_name, "nvim" | "vim" | "view" | "lvim") || process_name.starts_with("nvim-")
}

pub fn foreground_process_name(process_info_json: &str) -> Option<String> {
    let json: serde_json::Value = serde_json::from_str(process_info_json).ok()?;
    json.pointer("/result/process_info/foreground_processes/0/name")?
        .as_str()
        .filter(|name| !name.is_empty())
        .map(ToOwned::to_owned)
}

pub fn choose_command(
    pane_id: impl Into<String>,
    process_name: Option<&str>,
    direction: &str,
    key: &str,
) -> NavigatorCommand {
    let pane_id = pane_id.into();
    if process_name.is_some_and(is_vim_process) {
        NavigatorCommand::SendKeys {
            pane_id,
            key: key.to_string(),
        }
    } else {
        NavigatorCommand::Focus {
            pane_id,
            direction: direction.to_string(),
        }
    }
}

pub fn current_pane_id(current_pane_json: &str) -> Option<String> {
    let json: serde_json::Value = serde_json::from_str(current_pane_json).ok()?;
    json.pointer("/result/pane/pane_id")?
        .as_str()
        .filter(|pane_id| !pane_id.is_empty())
        .map(ToOwned::to_owned)
}

pub fn herdr_binary() -> OsString {
    std::env::var_os("HERDR_BIN_PATH").unwrap_or_else(|| OsString::from("herdr"))
}

pub fn env_pane_id() -> Option<String> {
    std::env::var("HERDR_ACTIVE_PANE_ID")
        .ok()
        .filter(|pane_id| !pane_id.is_empty())
        .or_else(|| {
            std::env::var("HERDR_PANE_ID")
                .ok()
                .filter(|pane_id| !pane_id.is_empty())
        })
}

pub fn command_output<I, S>(herdr: &OsStr, args: I) -> Result<String, String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let output = Command::new(herdr)
        .args(args)
        .output()
        .map_err(|err| err.to_string())?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

pub fn run_herdr<I, S>(herdr: &OsStr, args: I) -> Result<(), String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let status = Command::new(herdr)
        .args(args)
        .status()
        .map_err(|err| err.to_string())?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("herdr exited with status {status}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_vim_process_names() {
        for name in ["nvim", "vim", "view", "lvim", "nvim-qt"] {
            assert!(
                is_vim_process(name),
                "{name} should be detected as Vim-like"
            );
        }

        for name in ["bash", "fish", "node", "nvimfoo"] {
            assert!(
                !is_vim_process(name),
                "{name} should not be detected as Vim-like"
            );
        }
    }

    #[test]
    fn extracts_foreground_process_name_from_herdr_json() {
        let json = r#"{"result":{"process_info":{"foreground_processes":[{"name":"nvim"}]}}}"#;
        assert_eq!(Some("nvim".to_string()), foreground_process_name(json));
    }

    #[test]
    fn chooses_send_keys_for_vim_panes() {
        assert_eq!(
            NavigatorCommand::SendKeys {
                pane_id: "pane-1".into(),
                key: "alt+h".into()
            },
            choose_command("pane-1", Some("nvim"), "left", "alt+h")
        );
    }

    #[test]
    fn chooses_focus_for_non_vim_panes() {
        assert_eq!(
            NavigatorCommand::Focus {
                pane_id: "pane-1".into(),
                direction: "left".into()
            },
            choose_command("pane-1", Some("fish"), "left", "alt+h")
        );
    }

    #[test]
    fn extracts_current_pane_id_from_herdr_json() {
        let json = r#"{"result":{"pane":{"pane_id":"pane-9"}}}"#;
        assert_eq!(Some("pane-9".to_string()), current_pane_id(json));
    }

    #[test]
    fn command_args_match_herdr_cli() {
        assert_eq!(
            vec!["pane", "focus", "--direction", "right", "--pane", "pane-2"],
            NavigatorCommand::Focus {
                pane_id: "pane-2".into(),
                direction: "right".into()
            }
            .args()
        );
    }
}
