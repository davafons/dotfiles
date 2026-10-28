#!/usr/bin/env bash
# Claude Code status line, one line:
#   󰚩 Opus 5.5 ·  wariwari ·  lymx main+ · 󰧑 ██░░░░░░░░ 15% ·  5h 42% ↻44m ·  7d 12% ↻4d21h
# Claude pipes a JSON blob on stdin each refresh; `tee` it to a file to see every field.

input=$(cat)

# Fields are joined with \x1f, not tabs: read collapses runs of whitespace IFS,
# which would shift every field after an empty one.
IFS=$'\x1f' read -r model_id model dir ctx_used ctx_size ctx_pct rl5_pct rl5_reset rl7_pct rl7_reset < <(jq -r '[
	.model.id // "",
	(.model.display_name // "?" | sub("^Claude "; "")),
	.workspace.current_dir // .cwd // "",
	((.context_window.current_usage // {}) | (.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)),
	.context_window.context_window_size // 0,
	.context_window.used_percentage // "",
	.rate_limits.five_hour.used_percentage // "",
	.rate_limits.five_hour.resets_at // "",
	.rate_limits.seven_day.used_percentage // "",
	.rate_limits.seven_day.resets_at // ""
] | map(tostring) | join("\u001f")' <<<"$input")

DIM=$'\e[2m' BOLD=$'\e[1m' RESET=$'\e[0m'
BLUE=$'\e[34m' MAGENTA=$'\e[35m' CYAN=$'\e[36m' GREEN=$'\e[32m' YELLOW=$'\e[33m' RED=$'\e[31m'
# Nerd Font glyphs (the terminal font is HackGen Console NF).
I_MODEL=$'\U000f06a9' I_DIR=$'\uf07b' I_VCS=$'\ue725' I_WS=$'\U000f0645' I_CTX=$'\U000f09d1' I_5H=$'\uf017' I_7D=$'\uf073'
SEP=" ${DIM}·${RESET} "
now=$(date +%s)

# Green under 50%, yellow under 80%, red beyond.
level_color() {
	local p=${1%.*}
	if ((p >= 80)); then printf '%s' "$RED"
	elif ((p >= 50)); then printf '%s' "$YELLOW"
	else printf '%s' "$GREEN"; fi
}

# 10-cell bar for a percentage.
bar() {
	local p=$((${1%.*} > 100 ? 100 : ${1%.*})) i out=""
	for ((i = 0; i < 10; i++)); do
		((i < (p + 5) / 10)) && out+="█" || out+="░"
	done
	printf '%s' "$out"
}

# Seconds → "3d4h", "2h13m", "45m".
human_duration() {
	local s=$(($1 > 0 ? $1 : 0))
	if ((s >= 86400)); then printf '%dd%dh' $((s / 86400)) $((s % 86400 / 3600))
	elif ((s >= 3600)); then printf '%dh%02dm' $((s / 3600)) $((s % 3600 / 60))
	else printf '%dm' $((s / 60)); fi
}

out="${BOLD}${BLUE}${I_MODEL} ${model}${RESET}${SEP}${BLUE}${I_DIR} $(basename "$dir")${RESET}"

# jj: workspace (only when not default), change, bookmark (+ = above it).
# --ignore-working-copy keeps this read-only: no snapshot or op-log entry per refresh.
if root=$(cd "$dir" 2>/dev/null && jj root --ignore-working-copy 2>/dev/null); then
	jj=(jj --ignore-working-copy --no-pager --color=never -R "$root")
	at=$("${jj[@]}" log --no-graph -r @ -T 'change_id.short()' 2>/dev/null)
	ws=$("${jj[@]}" workspace list -T 'if(target.change_id().short() == "'"$at"'", name ++ "\n")' 2>/dev/null | head -1)
	bm=$("${jj[@]}" log --no-graph -r @ -T 'bookmarks.join(",")' 2>/dev/null)
	[[ -z $bm ]] && bm=$("${jj[@]}" log --no-graph -r 'heads(::@- & bookmarks())' -T 'bookmarks.join(",") ++ "+\n"' 2>/dev/null | head -1)
	vcs="${CYAN}${I_VCS}${RESET} "
	[[ -n $ws && $ws != default ]] && vcs+="${YELLOW}${I_WS} ${ws}${RESET} "
	vcs+="${MAGENTA}${at:0:4}${RESET}"
	[[ -n $bm ]] && vcs+=" ${GREEN}${bm}${RESET}"
	out+="$SEP$vcs"
elif branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short -q HEAD 2>/dev/null); then
	out+="$SEP${CYAN}${I_VCS}${RESET} ${GREEN}${branch}${RESET}"
fi

# Context, measured against the autocompact window when settings.json sets
# one for this model, since that is where the session actually compacts.
if [[ -n $ctx_pct ]]; then
	compact=$(jq -r --arg m "$model_id" '.modelSettings[$m].autoCompactWindow // empty' ~/.claude/settings.json 2>/dev/null)
	if [[ -n $compact ]] && ((compact > 0 && compact < ctx_size)); then
		ctx_pct=$((ctx_used * 100 / compact))
	fi
	c=$(level_color "$ctx_pct")
	out+="$SEP${DIM}${I_CTX}${RESET} ${c}$(bar "$ctx_pct") ${ctx_pct%.*}%${RESET}"
fi

# Subscription limits; only present on Pro/Max after the first response.
[[ -n $rl5_pct ]] && out+="$SEP${DIM}${I_5H} 5h${RESET} $(level_color "$rl5_pct")${rl5_pct%.*}%${RESET} ${DIM}↻$(human_duration $((rl5_reset - now)))${RESET}"
[[ -n $rl7_pct ]] && out+="$SEP${DIM}${I_7D} 7d${RESET} $(level_color "$rl7_pct")${rl7_pct%.*}%${RESET} ${DIM}↻$(human_duration $((rl7_reset - now)))${RESET}"

printf '%s' "$out"
