use zed_extension_api::{
    self as zed, settings::LspSettings, Command, LanguageServerId, Result, Worktree,
};

struct FortyTwoTuiActivity;

impl zed::Extension for FortyTwoTuiActivity {
    fn new() -> Self {
        Self
    }

    fn language_server_command(
        &mut self,
        _language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Command> {
        let settings = LspSettings::for_worktree("42tui-activity", worktree)?;
        let binary = settings.binary;
        let command = binary
            .as_ref()
            .and_then(|config| config.path.clone())
            .or_else(|| worktree.which("42tui-zed-lsp"))
            .ok_or_else(|| {
                "42tui-zed-lsp is not on PATH; install ft_tui or set lsp.42tui-activity.binary.path"
                    .to_string()
            })?;
        let args = binary
            .as_ref()
            .and_then(|config| config.arguments.clone())
            .unwrap_or_default();
        let mut env = worktree.shell_env();
        if let Some(overrides) = binary.and_then(|config| config.env) {
            for (key, value) in overrides {
                if let Some(existing) = env.iter_mut().find(|(existing_key, _)| existing_key == &key) {
                    *existing = (key, value);
                } else {
                    env.push((key, value));
                }
            }
        }

        Ok(Command {
            command,
            args,
            env,
        })
    }
}

zed::register_extension!(FortyTwoTuiActivity);
