alias reload='. ~/.bashrc' # WoW style bash reload

alias vims='sudo -E nvim'
alias vim="nvim"

# Program aliases
alias g='git'
alias y='yadm'

# Git aliases
alias g='git'
alias gcl='git clone'
alias gbr='git branch'
alias glog='git log'
alias gfe='git fetch'
alias gco='git checkout'
alias gcm='git checkout master'
alias gst='git status'
alias gd='git diff'
alias gdc='git diff --cached'
alias gdd='git diff --cached develop'
alias gca='git commit -a'
alias ga='git add'
alias glr='git pull --rebase'
alias grbiom='git rebase --interactive origin/master'
alias grba='git rebase --abort'
alias grbc='git rebase --continue'
alias grma='git merge --abort'
alias grmc='git merge --continue'
alias gsta='git stash'
alias gstop='git stash pop'
alias gcp='git cherry-pick'
alias gcpa='git cherry-pick --abort'
alias gcpc='git cherry-pick --continue'
alias vim='nvim'

alias gg='./gradlew'
alias ggb="./gradlew bootRun"
alias ggr="./gradlew resetLocalEnv"
alias ggrb="./gradlew resetLocalEnv && ./gradlew bootRun"
alias ggt="./gradlew test"
alias ggs="./gradlew spotlessApply"

alias batteryUsage='upower -i /org/freedesktop/UPower/devices/battery_BAT0'

alias claude="/home/davafons/.claude/local/claude"
