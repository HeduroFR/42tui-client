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

Existing checkouts are fetched and inspected without overwriting files, changing
branches or replacing remote configuration. If a remote has commits missing
locally, editor launch stops for manual reconciliation. Inspect the fetched history
and reconcile it yourself, then retry. If Vogsphere is unreachable, an existing
checkout with committed work still opens with a warning; its remote history will
be checked again on the next editor launch. New, empty and unborn checkouts must
complete recovery first. Setup never resets or force-pushes work.

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
