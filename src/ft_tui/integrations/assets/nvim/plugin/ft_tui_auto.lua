-- Load the packaged integration without editing the user's init.lua.
local module = require("ft_tui")
if not module._configured then
  local ok, config = pcall(require, "ft_tui_config")
  module.setup(ok and config or {})
end
