# Git Command Reference (Beyond the Basics)

Source material for `scenarios/git/`. The everyday flow (branch, commit,
push, PR, merge/rebase basics, tags, bisect) is taught in the CI/CD
category; this file goes deeper.

## How Git Stores Things

```
git cat-file -t <sha>            # object type: blob, tree, commit, tag
git cat-file -p <sha>            # print an object
git ls-tree HEAD
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
git show-ref
git count-objects -vH
git fsck --lost-found
git gc
```

## Staging Precisely

```
git add -p
git diff                          # unstaged
git diff --staged                 # staged
git restore --staged <file>       # unstage
git restore <file>                # discard working-tree changes
git commit --amend --no-edit
git commit --fixup <sha>
git rm --cached <file>
```

## Branches

```
git switch <branch>
git switch -c <branch>
git branch -vv
git branch --merged main
git branch -d <branch>            # -D to force
git push -u origin <branch>
git fetch --prune
git branch -m <old> <new>
```

## Merging & Conflicts

```
git merge --no-ff <branch>
git merge --abort
git status
git diff --name-only --diff-filter=U
git checkout --ours <file>        # or --theirs
git merge --continue
git config rerere.enabled true
git mergetool
```

## Rebasing

```
git rebase main
git rebase -i --autosquash main
git rebase --onto <newbase> <upstream> <branch>
git rebase --continue | --abort | --skip
git pull --rebase
git range-diff main@{u} main
```

## Undoing

```
git restore <file>
git reset --soft HEAD~1           # keep changes staged
git reset --mixed HEAD~1          # keep changes unstaged (default)
git reset --hard HEAD~1           # discard changes
git reset --hard ORIG_HEAD
git revert <sha>
git revert -m 1 <merge-sha>
git reflog
git branch <name> <sha>
```

## Searching History

```
git log --oneline --graph --all
git log -S '<string>'             # commits that added/removed a string
git log -G '<regex>'
git log --follow -- <file>
git log -p -- <file>
git blame -L <start>,<end> <file>
git blame -w -C <file>
git shortlog -sn
git grep -n '<pattern>'
git show <sha>:<path>
```

## Remotes & Collaboration

```
git remote -v
git remote add upstream <url>
git fetch upstream
git pull --ff-only
git push --force-with-lease
git push origin --delete <branch>
git branch -u origin/<branch>
git cherry -v main
```

## Stash & Worktrees

```
git stash push -m "<message>"
git stash push -u                 # include untracked files
git stash list
git stash show -p stash@{0}
git stash apply | pop
git stash branch <branch>
git worktree add ../<dir> <branch>
git worktree list
git worktree remove ../<dir>
```

## Config, Ignore, Attributes, Hooks

```
git config --global alias.<name> '<command>'
git config --list --show-origin
git check-ignore -v <path>
git status --ignored
git add --renormalize .
git config core.hooksPath .githooks
git config --global pull.rebase true
git config --global init.defaultBranch main
```

## Large and Unusual Repositories

```
git clone --depth 1 <url>
git clone --filter=blob:none <url>
git sparse-checkout set <dir> <dir>
git submodule add <url> <path>
git submodule update --init --recursive
git submodule status
git lfs install
git lfs track "*.psd"
git lfs ls-files
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)'
git filter-repo --strip-blobs-bigger-than 50M
```

## Signing & Verification

```
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git commit -S -m "<message>"
git log --show-signature -1
git tag -s v1.0.0 -m "<message>"
git verify-tag v1.0.0
```
