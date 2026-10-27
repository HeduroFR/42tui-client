" 42TUI editor activity integration for Vim 8.2+.
if exists('g:loaded_ft_tui')
  finish
endif
let g:loaded_ft_tui = 1

if !exists('g:ft_tui_command')
  let g:ft_tui_command = '42tui'
endif
if !exists('g:ft_tui_min_interval')
  let g:ft_tui_min_interval = 30
endif

let s:last_sent = 0
let s:timer = -1
let s:pending_file = ''
let s:pending_write = 0

function! s:SendPending(timer) abort
  let s:timer = -1
  if empty(s:pending_file)
    return
  endif
  let l:file = s:pending_file
  let l:is_write = s:pending_write
  let s:pending_file = ''
  let s:pending_write = 0
  let s:last_sent = localtime()

  let l:argv = [g:ft_tui_command, 'heartbeat', '--file', l:file,
        \ '--editor', 'vim', '--quiet']
  if l:is_write
    call add(l:argv, '--write')
  endif
  if exists('*job_start')
    call job_start(l:argv, {'in_io': 'null', 'out_io': 'null', 'err_io': 'null'})
  else
    " Keep paths and executable names safe when running through the shell.
    let l:command = join(map(copy(l:argv), 'shellescape(v:val)'), ' ')
    call system(l:command)
  endif
endfunction

function! s:Heartbeat(is_write) abort
  if &buftype !=# '' || empty(expand('%:p'))
    return
  endif
  let s:pending_file = expand('%:p')
  let s:pending_write = s:pending_write || a:is_write
  let l:interval = max([1, get(g:, 'ft_tui_min_interval', 30)])
  let l:remaining = l:interval - (localtime() - s:last_sent)
  if l:remaining <= 0
    if s:timer != -1
      call timer_stop(s:timer)
      let s:timer = -1
    endif
    call s:SendPending(-1)
  elseif s:timer == -1
    let s:timer = timer_start(l:remaining * 1000, function('<SID>SendPending'))
  endif
endfunction

augroup ft_tui_heartbeat
  autocmd!
  autocmd BufEnter * call <SID>Heartbeat(0)
  autocmd TextChanged,TextChangedI * call <SID>Heartbeat(0)
  autocmd BufWritePost * call <SID>Heartbeat(1)
augroup END
