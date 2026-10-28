# Project Git workflow

Configure the local folder and development/Vogsphere URLs in project settings.
The project controls and `42git` share the same Git operations.

## Recover work before editing

Before the first editor launch in an app session, setup recovers existing
Vogsphere work into a new or empty folder. If Vogsphere is empty, it uses the
development repository; if both are empty, it initializes a local repository.

Existing checkouts are fetched and inspected without overwriting files, changing
branches or replacing remote configuration. If a remote has commits missing
locally, editor launch stops for manual reconciliation. Inspect the fetched history
and reconcile it yourself, then retry. Setup never resets or force-pushes work.

## Publish committed work

Run `42git status` inside a configured project folder, including its subfolders.
Unlike `42goto`, it does not select a different project from recent activity.

| Action | Destination branch |
| --- | --- |
| Push dev / `42git push dev` | Current branch on the development remote |
| Push Vogsphere / `42git push vog` | `master` on Vogsphere |
| Push all / `42git push all` | Both, with separate results |

Review the committed revision, destination and branch before confirming. Both
destinations receive the reviewed commit and its history. Local edits remain
untouched: stage and commit them yourself if you want to publish them. Detached
HEAD, missing commits and unresolved merge conflicts must be resolved first.

Pushes preserve pre-push hooks and never force remote history. If the branch,
commit or destination changes after review, review again before retrying.

## Failed and partial pushes

Push all can succeed for one destination and fail for the other. The TUI offers
a review and retry for just the failed destination; in the shell, repeat its
individual command. Check authentication, connectivity and rejected-history
errors before retrying. After a timeout or interruption, inspect the remote first:
the push may have completed even if its response was lost.

If an existing remote URL conflicts with project settings, or Git has ambiguous
fetch/push URLs, resolve that configuration manually. No remote is silently replaced.
