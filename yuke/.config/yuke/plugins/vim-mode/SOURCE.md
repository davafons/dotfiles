# Vim source

This personal plugin uses xyaman's Vim implementation at dotfiles revision `3828de16e12a0b6f55de939ef2035e2049fe631e`.

Source: <https://github.com/xyaman/dotfiles/tree/3828de16e12a0b6f55de939ef2035e2049fe631e/yuke/.config/yuke/plugins/vim-mode>

Local changes replace private UI access with supported owner operations. They add typed mode transitions and optional display-row movement. The operator parser and native visual-put repeat remain upstream's implementation. The read-only transcript prefix parser also emits a local file-opening event for Normal-mode `gf`; the Herdr integration owns path lookup and editor activation. Replace mode is not supported.

No reuse license appeared in the inspected tree. This copy is for personal use. Confirm reuse terms before redistribution.
