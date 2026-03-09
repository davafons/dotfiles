alias reload='. ~/.bashrc' # WoW style bash reload

alias vims='sudo -E nvim'
alias vim="nvim"

# Program aliases
alias g='git'
alias y='yadm'

# Git aliases
alias g='git'
alias vim='nvim'

alias gg='./gradlew'
alias ggb="./gradlew bootRun"
alias ggr="./gradlew resetLocalEnv"
alias ggrb="./gradlew resetLocalEnv && ./gradlew bootRun"
alias ggt="./gradlew test"
alias ggs="./gradlew spotlessApply"

alias batteryUsage='upower -i /org/freedesktop/UPower/devices/battery_BAT0'

# 3D printing - fix Wayland OpenGL viewport
alias bambu-studio='__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json bambu-studio'
