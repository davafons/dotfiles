#!/bin/bash

input=$(cat)
model_raw=$(echo "$input" | jq -r '.model.display_name' | sed 's/Claude //')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
project_dir=$(echo "$input" | jq -r '.workspace.project_dir')
output_style=$(echo "$input" | jq -r '.output_style.name')

model="[${model_raw}]"

cost=$(echo "$input" | jq -r '.cost.total_cost_usd')
if [ "$cost" != "null" ] && [ "$cost" != "0" ]; then
    cost_display=$(printf "%.4f" "$cost")
    cost_info="💰 \$$cost_display"
else
    cost_info=""
fi

usage=$(echo "$input" | jq '.context_window.current_usage')
if [ "$usage" != "null" ]; then
    current=$(echo "$usage" | jq '.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens')
    size=$(echo "$input" | jq '.context_window.context_window_size')
    pct=$((current * 100 / size))
    if [ "$current" -ge 1000000 ]; then
        token_display=$(echo "scale=1; $current / 1000000" | bc)"M"
    elif [ "$current" -ge 1000 ]; then
        token_display=$(echo "scale=1; $current / 1000" | bc)"K"
    else
        token_display="$current"
    fi
    token_info="🪙 $token_display | $pct%"
else
    token_info=""
fi

project_name=$(basename "$project_dir")
current_name=$(basename "$current_dir")

if [ "$current_dir" = "$project_dir" ]; then
    dir_info="📁 $project_name"
else
    if [ -n "$project_dir" ] && [[ "$current_dir" == "$project_dir"* ]]; then
        rel_path=${current_dir#$project_dir/}
        if [[ "$rel_path" == */* ]]; then
            parent=$(basename "$(dirname "$current_dir")")
            dir_info="📁 $project_name | 📂 $parent/$current_name"
        else
            dir_info="📁 $project_name | 📂 $current_name"
        fi
    else
        dir_info="📂 $current_name"
    fi
fi

git_info=""
if git -C "$current_dir" --no-optional-locks rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$current_dir" --no-optional-locks branch --show-current 2>/dev/null)
    if [ -n "$branch" ]; then
        status=$(git -C "$current_dir" --no-optional-locks status --porcelain 2>/dev/null)
        if [ -n "$status" ]; then
            git_info="$branch*"
        else
            git_info="$branch✓"
        fi
    fi
fi

if [ -n "$git_info" ]; then
    dir_info="$dir_info | $git_info"
fi

style_info=""
if [ "$output_style" != "default" ] && [ -n "$output_style" ]; then
    style_info="| $output_style"
fi

parts=("$model")
if [ -n "$cost_info" ]; then
    parts+=("$cost_info")
fi
if [ -n "$token_info" ]; then
    parts+=("$token_info")
fi
parts+=("$dir_info")
if [ -n "$style_info" ]; then
    parts+=("$style_info")
fi

IFS=" | "
printf '%s' "${parts[*]}"
unset IFS
