# Project Git workflow

Configure the local folder and development/Vogsphere URLs in project settings.
The project controls and `42git` share the same Git operations.

Vogsphere requires the 42 campus network. Pushes are unavailable outside campus;
return to campus before retrying. A development remote has its own network and
authentication requirements. Real Vogsphere validation must run on campus with
the student's existing Git/SSH authentication.

## Between campus and home

1. On campus, commit your work and use **Push all** (`42git push all`).
2. At home, update your development checkout, work and commit, then use
   **Push dev** (`42git push dev`). Vogsphere waits until you return to campus.
3. Back on campus, fetch the development remote and fast-forward your local
   branch before pushing to both destinations again. Run this inside the
   configured project folder:

   ```sh
   42git pull dev
   42git push all
   ```

Commit or move local edits before pulling. If a fast-forward is impossible,
reconcile the branches yourself;
42TUI never resets, stashes, merges or commits your work automatically.

## Recover work before editing

Before the first editor launch in an app session, setup recovers existing
Vogsphere work into a new or empty folder. If Vogsphere is empty, it uses the
development repository; if both are empty, it initializes a local repository.

Editor recovery reuses completed remote checks for five minutes in the same app
session when local files, HEAD, branches, index, remote configuration and operation
state remain unchanged. This caches results, not passphrases. Local changes or
expiry trigger a new check; remote-only changes can remain unseen until expiry.
Authentication failures and off-campus warnings are not cached. Pull and push
always revalidate their own plans before writing.

Editor recovery displays a cancellable loading dialog while checking remotes.
If OpenSSH needs a key passphrase, enter it in the masked SSH authentication
dialog. The app reuses the same key passphrase in memory across connections
within that operation, so checking and fetching do not ask twice. If SSH rejects
a value and retries, enter it again. The value is discarded when the operation
ends. Existing SSH configuration and agents still apply. Cancel prevents the editor from
opening; an already-running Git check may finish in the background.

Existing checkouts are fetched and inspected without overwriting files, changing
branches or replacing remote configuration. If a remote has commits missing
locally, a review dialog shows the fetched remote snapshot, local branch, working
changes and a read-only diff of the remote snapshot against tracked local files.
The source is labelled **dev (origin)** or **vog (vogsphere)** with its branch,
credential-redacted URL and local/remote unique commit counts. Suggested terminal
commands depend on the history: review `42git pull dev|vog` for a compatible
fast-forward, address local blockers first, or inspect divergent/unrelated
commits before choosing a manual reconciliation. Use **Pull dev/vog**, **Push
dev/vog**, **Inspect commits** or **Git status** to open an output modal. Pull
and push show a captured plan and require confirmation; they recheck branch,
HEAD, destination and remote history before writing. A stale review is blocked.
Pull remains fast-forward-only; no automatic merge, rebase, stash or reset is
introduced. Close the output modal to refresh the review. Terminal commands
remain available as alternatives, and action buttons have separate spacing.
Untracked files are listed separately; their contents are not included in the diff.
Choose **Open local files** to inspect or resolve the differences in your editor,
or **Cancel**. Opening files does not pull, merge, reset or overwrite work;
reconcile histories explicitly before synchronizing. If Vogsphere is unreachable,
an existing checkout with committed work still opens with a warning; its remote
history will be checked again on the next editor launch. New or empty folders
must complete recovery first. Existing Git folders without a local commit can
also be reviewed and opened explicitly. Setup never resets or force-pushes work.

## Publish committed work

Run `42git status` inside a configured project folder, including its subfolders.
Unlike `42goto`, it does not select a different project from recent activity.

| Action | Destination branch |
| --- | --- |
| Push dev / `42git push dev` | Current branch on the development remote |
| Push Vogsphere / `42git push vog` | Advertised default branch, or the only remote branch |
| Push all / `42git push all` | Both, with separate results |

Review the committed revision, destination and branch before confirming. Both
destinations receive the reviewed commit and its history. Local edits remain
untouched: stage and commit them yourself if you want to publish them. Detached
HEAD, missing commits and unresolved merge conflicts must be resolved first.

Pushes preserve pre-push hooks and never force remote history. If the branch,
commit or destination changes after review, review again before retrying.

Vogsphere recovery and push use the remote's advertised default branch (`main`,
`master` or another name), falling back to its only branch. Multiple branches with
no valid advertised default require manual resolution. An empty Vogsphere remote
receives the current local branch, shown in the push review. Development pushes
continue to use the current local branch.

## Pull committed work

Use `42git pull dev`, `42git pull vog`, or `42git pull all` inside the configured
project folder or a subfolder. Fetching prepares a review of source URLs, branch
names, fetched commits and the proposed local revision. Confirm before updating.
Cancelling leaves fetched objects available, without changing local HEAD or files.

Development pulls use the current branch when it exists remotely, otherwise the
advertised default or only branch. Vogsphere uses its advertised default or only
branch. Missing, unreachable, empty or ambiguous selected remotes stop the pull.
`pull all` requires both remotes: both are fetched before any local fast-forward.
Local and remote revisions must form one ancestor chain; if they diverge, resolve
it manually or pull from a single chosen source. A local branch already ahead is
kept intact. Pull never pushes anything back to either remote.

The checkout must be clean, including untracked files, without an unfinished
merge/rebase/cherry-pick. Pull never stashes, resets, switches branches or creates
a merge commit, and protects ignored files from overwrite. Changes to local HEAD,
source URL, branch or remote commit invalidate the review. Vogsphere access still
requires the campus network; use `pull dev` at home.

## Failed and partial pushes

Push all can succeed for one destination and fail for the other. The TUI offers
a review and retry for just the failed destination; in the shell, repeat its
individual command. Check authentication, connectivity and rejected-history
errors before retrying. After a timeout or interruption, inspect the remote first:
the push may have completed even if its response was lost.

If an existing remote URL conflicts with project settings, or Git has ambiguous
fetch/push URLs, resolve that configuration manually. No remote is silently replaced.
