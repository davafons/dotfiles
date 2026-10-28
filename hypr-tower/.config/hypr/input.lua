-- Personal input overrides, loaded after Omarchy's defaults.
-- Ported from hypr/.config/hypr/input.conf. Device-specific rules for the
-- physical keyboard and mouse are omitted: tower is driven over Moonlight.
hl.config({
  input = {
    kb_layout = "us",
    kb_variant = "intl",
    kb_options = "compose:caps",
    repeat_rate = 40,
    repeat_delay = 600,
    numlock_by_default = true,
    float_switch_override_focus = 0,
    sensitivity = -0.8,
    touchpad = {
      scroll_factor = 0.4,
    },
  },
  cursor = {
    no_warps = true,
  },
})
