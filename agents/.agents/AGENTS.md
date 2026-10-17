# Version control

Check for `.jj/` at the repository root before running version-control commands.
If present, use jj instead of Git, including in colocated repositories.
Never mutate Git there or fall back to Git because a jj command failed.
Use `jj diff --git` for diffs and `jj push` for authorized pushes.
Use Git only in repositories without `.jj/`.

Never add AI co-author trailers such as `Co-authored-by: Claude` to commit messages.
Never add AI attribution such as "Generated with Claude" to commit messages or pull request descriptions.
