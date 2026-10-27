-- 42TUI editor activity integration for Neovim 0.8+.
local M = {}
local clock = vim.uv or vim.loop
local last_sent
local timer_pending = false
local pending_file
local pending_write = false

M.command = "42tui"
M.min_interval = 30

local function send_pending()
  timer_pending = false
  if not pending_file then
    return
  end
  local file = pending_file
  local is_write = pending_write
  pending_file = nil
  pending_write = false
  last_sent = clock.now()

  local argv = { M.command, "heartbeat", "--file", file, "--editor", "nvim", "--quiet" }
  if is_write then
    table.insert(argv, "--write")
  end
  vim.fn.jobstart(argv, { detach = true, stdout_buffered = false, stderr_buffered = false })
end

local function heartbeat(is_write)
  local file = vim.api.nvim_buf_get_name(0)
  if file == "" or vim.bo.buftype ~= "" then
    return
  end
  pending_file = file
  pending_write = pending_write or is_write

  local interval_ms = math.max(1, tonumber(M.min_interval) or 30) * 1000
  local remaining = last_sent and (interval_ms - (clock.now() - last_sent)) or 0
  if remaining <= 0 then
    send_pending()
  elseif not timer_pending then
    timer_pending = true
    vim.defer_fn(send_pending, remaining)
  end
end

function M.setup(opts)
  opts = opts or {}
  M.command = opts.command or M.command
  M.min_interval = opts.min_interval or M.min_interval

  local group = vim.api.nvim_create_augroup("FtTuiHeartbeat", { clear = true })
  vim.api.nvim_create_autocmd({ "BufEnter", "TextChanged", "TextChangedI" }, {
    group = group,
    callback = function()
      heartbeat(false)
    end,
  })
  vim.api.nvim_create_autocmd("BufWritePost", {
    group = group,
    callback = function()
      heartbeat(true)
    end,
  })
end

return M
