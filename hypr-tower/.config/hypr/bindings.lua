-- Personal keybinding overrides, loaded after Omarchy's defaults.
-- See current bindings: omarchy menu keybindings --print

o.bind("SUPER + SHIFT + T", "Activity", "omarchy-launch-tui btop")

o.bind("SUPER + D", "Launch apps", "omarchy-menu toggle apps")
-- Was: Docker
hl.unbind("SUPER + SHIFT + D")
o.bind("SUPER + SHIFT + D", "Omarchy menu", "omarchy-menu toggle")
-- Was: Email
hl.unbind("SUPER + SHIFT + E")
o.bind("SUPER + SHIFT + E", "Power menu", "omarchy-menu toggle system")

-- Vim-style focus and movement. Was: J toggle split, K keybindings, L layout toggle.
hl.unbind("SUPER + J")
hl.unbind("SUPER + K")
hl.unbind("SUPER + L")
o.bind("SUPER + H", "Focus on left window", hl.dsp.focus({ direction = "l" }))
o.bind("SUPER + L", "Focus on right window", hl.dsp.focus({ direction = "r" }))
o.bind("SUPER + K", "Focus on above window", hl.dsp.focus({ direction = "u" }))
o.bind("SUPER + J", "Focus on below window", hl.dsp.focus({ direction = "d" }))
o.bind("SUPER + SHIFT + H", "Move window left", hl.dsp.window.move({ direction = "l" }))
o.bind("SUPER + SHIFT + L", "Move window right", hl.dsp.window.move({ direction = "r" }))
o.bind("SUPER + SHIFT + K", "Move window up", hl.dsp.window.move({ direction = "u" }))
o.bind("SUPER + SHIFT + J", "Move window down", hl.dsp.window.move({ direction = "d" }))

-- Was: toggle window grouping
hl.unbind("SUPER + G")
o.bind("SUPER + G", "Shrink split", hl.dsp.layout("splitratio -0.48"))

-- Was: Music
hl.unbind("SUPER + SHIFT + M")
o.bind("SUPER + M", "Screenshot with editing", "omarchy-capture-screenshot")
o.bind("SUPER + SHIFT + M", "Screenshot to clipboard", "omarchy-capture-screenshot smart copy")
o.bind("SUPER + ALT + M", "Screenrecording", "omarchy-capture-screenrecording --stop-recording || omarchy-menu toggle trigger.capture.screenrecord")
-- Was: Music TUI
hl.unbind("SUPER + SHIFT + ALT + M")
o.bind("SUPER + SHIFT + ALT + M", "Color picker", "pkill hyprpicker || hyprpicker -a")
