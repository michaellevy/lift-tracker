library(ggplot2)
library(dplyr)
library(lubridate)
library(scales)
library(tidyr)
library(forcats)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
args <- commandArgs(trailingOnly = FALSE)
file_flag <- grep("--file=", args, value = TRUE)
if (length(file_flag)) {
  # Called via Rscript: resolve relative to the script file
  script_dir <- dirname(normalizePath(sub("--file=", "", file_flag)))
} else if (file.exists(file.path(getwd(), "entries.csv"))) {
  # Interactive, working dir is scripts/
  script_dir <- getwd()
} else {
  # Interactive from RStudio Rproj root: entries.csv is in scripts/
  script_dir <- file.path(getwd(), "scripts")
}
csv_path <- file.path(script_dir, "entries.csv")
df <- read.csv(csv_path, stringsAsFactors = FALSE)
df$date   <- as.Date(df$date)
df$weight <- as.numeric(df$weight)
df$sets   <- as.integer(df$sets)
df$reps   <- as.integer(df$reps)
df$flag   <- ifelse(is.na(df$flag), "", df$flag)
df$volume <- df$sets * df$reps * df$weight

# ---------------------------------------------------------------------------
# Lift definitions
# ---------------------------------------------------------------------------
current_lifts <- c(
  "barbell_bench_press", "trap_bar_deadlift", "row", "weighted_pull_ups",
  "db_incline_press", "dips", "rdl", "seated_hamstring_curl",
  "triceps_pushdown", "incline_db_curl", "face_pull", "rear_delt_fly",
  "lateral_raise", "hammer_curl", "overhead_triceps_extension",
  "straight_arm_pulldown", "glute_kickback", "hip_abduction",
  "leg_press", "box_jumps", "pallof_press", "cable_rotation", "db_flat_bench"
)

historical_lifts <- c(
  "back_squat", "deadlift", "strict_press", "front_squat",
  "hip_thrust", "bulgarian_split_squat", "lat_pulldown",
  "calf_raise", "hanging_leg_raise", "leg_extension", "hip_adduction",
  "walking_lunge", "step_ups"
)

all_featured <- c(current_lifts, historical_lifts)

lift_labels <- c(
  barbell_bench_press        = "Bench Press",
  trap_bar_deadlift          = "Trap Bar DL",
  row                        = "Row",
  weighted_pull_ups          = "Weighted Pull-Ups",
  db_incline_press           = "DB Incline Press",
  dips                       = "Dips",
  rdl                        = "Romanian DL",
  seated_hamstring_curl      = "Hamstring Curl",
  triceps_pushdown           = "Triceps Pushdown",
  incline_db_curl            = "Incline DB Curl",
  face_pull                  = "Face Pull",
  rear_delt_fly              = "Rear Delt Fly",
  lateral_raise              = "Lateral Raise",
  hammer_curl                = "Hammer Curl",
  overhead_triceps_extension = "OH Triceps Ext",
  straight_arm_pulldown      = "Straight-Arm Pulldown",
  glute_kickback             = "Glute Kickback",
  hip_abduction              = "Hip Abduction",
  leg_press                  = "Leg Press",
  box_jumps                  = "Box Jumps",
  pallof_press               = "Pallof Press",
  cable_rotation             = "Cable Rotation",
  db_flat_bench              = "DB Flat Bench",
  back_squat                 = "Back Squat",
  deadlift                   = "Deadlift",
  strict_press               = "Strict Press",
  front_squat                = "Front Squat",
  hip_thrust                 = "Hip Thrust",
  bulgarian_split_squat      = "Bulgarian Split Squat",
  lat_pulldown               = "Lat Pulldown",
  calf_raise                 = "Calf Raise",
  hanging_leg_raise          = "Hanging Leg Raise",
  leg_extension              = "Leg Extension",
  hip_adduction              = "Hip Adduction",
  walking_lunge              = "Walking Lunge",
  step_ups                   = "Step-Ups"
)

df <- df %>%
  mutate(lift_label = coalesce(lift_labels[lift_id], lift_name))

# ---------------------------------------------------------------------------
# Per-session max weight (with flag carried forward)
# ---------------------------------------------------------------------------
qualifying <- df %>%
  filter(lift_id %in% all_featured, weight > 0) %>%
  group_by(lift_id) %>%
  filter(n_distinct(date) >= 3) %>%
  ungroup()

max_weight_per_session <- qualifying %>%
  group_by(lift_id, lift_label, date) %>%
  summarise(
    max_weight   = max(weight),
    total_volume = sum(volume),
    flag         = paste(unique(flag[flag != ""]), collapse = "; "),
    .groups      = "drop"
  ) %>%
  mutate(
    in_current = lift_id %in% current_lifts,
    is_flagged = flag != "",
    flag_type  = ifelse(is_flagged,
                        sub(":.*", "", sub(";.*", "", trimws(flag))),
                        "ok")
  )

# ---------------------------------------------------------------------------
# Shared theme
# ---------------------------------------------------------------------------
theme_lift <- theme_minimal(base_size = 11) +
  theme(
    plot.title       = element_text(face = "bold", size = 14, margin = margin(b = 4)),
    plot.subtitle    = element_text(size = 9.5, color = "gray45", margin = margin(b = 8)),
    strip.text       = element_text(face = "bold", size = 9),
    panel.grid.minor = element_blank(),
    panel.grid.major = element_line(color = "gray92"),
    axis.text        = element_text(size = 8.5, color = "gray40"),
    axis.title.y     = element_text(size = 9.5, color = "gray30"),
    legend.position  = "bottom",
    legend.text      = element_text(size = 9),
    plot.margin      = margin(12, 14, 8, 12)
  )

# Colour palette for flag types
flag_colors <- c(
  weight_drop         = "#e74c3c",
  weight_jump_up      = "#e67e22",
  zero_weight_barbell = "#8e44ad",
  high_volume         = "#27ae60",
  ok                  = "#4472C4"
)

# Minimum sessions required before drawing a LOESS smoother
smooth_min <- 6

out_dir <- script_dir

# ---------------------------------------------------------------------------
# Chart 1: Weight over time — current program lifts
# ---------------------------------------------------------------------------
curr_data <- max_weight_per_session %>%
  filter(in_current, !lift_id %in% c("box_jumps", "pallof_press", "cable_rotation"))

# Restrict smoother to lifts with enough sessions to avoid degenerate fits
smooth_lifts_curr <- curr_data %>%
  count(lift_id) %>%
  filter(n >= smooth_min) %>%
  pull(lift_id)

p1 <- ggplot(curr_data, aes(x = date, y = max_weight)) +
  # Draw smoother first so it sits behind the points
  geom_smooth(
    data        = filter(curr_data, lift_id %in% smooth_lifts_curr),
    method      = "loess", span = 0.75, se = FALSE,
    method.args = list(degree = 1),
    color = "#e15759", linewidth = 0.85, na.rm = TRUE
  ) +
  geom_point(data = filter(curr_data, !is_flagged),
             color = "#4472C4", alpha = 0.70, size = 2.0) +
  geom_point(data = filter(curr_data, is_flagged),
             aes(fill = flag_type), shape = 21, size = 3,
             stroke = 1.4, color = "#7b241c", alpha = 0.95) +
  facet_wrap(~ lift_label, scales = "free_y", ncol = 4) +
  scale_x_date(date_breaks = "3 months", date_labels = "%b\n'%y") +
  scale_fill_manual(values = flag_colors, guide = "none") +
  labs(
    title    = "Current Program — Weight Over Time",
    subtitle = "Points = max weight per session · Red line = LOESS trend (lifts with ≥ 6 sessions)",
    x = NULL, y = "Weight (lbs)"
  ) +
  theme_lift

ggsave(file.path(out_dir, "chart1_current_program.png"), p1,
       width = 14, height = 12, dpi = 150)
message("Saved chart1_current_program.png")

# ---------------------------------------------------------------------------
# Chart 2: Six key lifts — multi-line weight comparison
# ---------------------------------------------------------------------------
key_lifts <- c("barbell_bench_press", "trap_bar_deadlift", "rdl",
               "weighted_pull_ups",   "back_squat",        "dips")

comp_data <- max_weight_per_session %>%
  filter(lift_id %in% key_lifts)

# Hand-picked distinct palette for 6 lines
comp_colors <- c(
  "Bench Press"       = "#4472C4",
  "Trap Bar DL"       = "#ED7D31",
  "Romanian DL"       = "#70AD47",
  "Weighted Pull-Ups" = "#9E480E",
  "Back Squat"        = "#997300",
  "Dips"              = "#833C00"
)

smooth_lifts_comp <- comp_data %>%
  count(lift_id) %>%
  filter(n >= smooth_min) %>%
  pull(lift_id)

p2 <- ggplot(comp_data, aes(x = date, y = max_weight, color = lift_label)) +
  geom_smooth(
    data   = filter(comp_data, lift_id %in% smooth_lifts_comp),
    method = "loess", span = 0.65, se = FALSE,
    linewidth = 1.3, na.rm = TRUE
  ) +
  geom_point(data = filter(comp_data, !is_flagged), alpha = 0.5, size = 1.8) +
  geom_point(data = filter(comp_data, is_flagged),
             size = 3.5, shape = 24, fill = "#e74c3c", color = "#7b241c",
             stroke = 1.2, alpha = 0.95) +
  scale_x_date(date_breaks = "2 months", date_labels = "%b '%y") +
  scale_color_manual(values = comp_colors) +
  labs(
    title    = "Key Lifts — Weight Over Time",
    subtitle = "Solid lines = LOESS trend · Solid triangles = flagged entries",
    x = NULL, y = "Weight (lbs)", color = NULL
  ) +
  theme_lift +
  guides(color = guide_legend(nrow = 2, override.aes = list(size = 3, alpha = 1,
                                                             linewidth = 1.5)))

ggsave(file.path(out_dir, "chart2_compound_lifts.png"), p2,
       width = 12, height = 7, dpi = 150)
message("Saved chart2_compound_lifts.png")

# ---------------------------------------------------------------------------
# Chart 3: Estimated 1RM (Epley) for key barbell lifts
# ---------------------------------------------------------------------------
barbell_lifts <- c("barbell_bench_press", "back_squat",
                   "deadlift", "trap_bar_deadlift", "strict_press",
                   "rdl", "front_squat")

e1rm_data <- df %>%
  filter(lift_id %in% barbell_lifts, weight > 0, reps >= 1, reps <= 12) %>%
  mutate(e1rm = weight * (1 + reps / 30)) %>%
  group_by(lift_id, lift_label, date) %>%
  summarise(
    best_e1rm = max(e1rm, na.rm = TRUE),
    flag      = paste(unique(flag[flag != ""]), collapse = "; "),
    .groups   = "drop"
  ) %>%
  mutate(
    is_flagged = flag != "",
    flag_type  = ifelse(is_flagged,
                        sub(":.*", "", sub(";.*", "", trimws(flag))),
                        "ok")
  )

smooth_lifts_e1rm <- e1rm_data %>%
  count(lift_id) %>%
  filter(n >= smooth_min) %>%
  pull(lift_id)

p3 <- ggplot(e1rm_data, aes(x = date, y = best_e1rm)) +
  geom_smooth(
    data    = filter(e1rm_data, lift_id %in% smooth_lifts_e1rm),
    method  = "loess", span = 0.75, se = TRUE,
    fill    = "#d0cde1", color = "#54278f", linewidth = 0.9,
    alpha   = 0.25, na.rm = TRUE
  ) +
  geom_point(data = filter(e1rm_data, !is_flagged),
             color = "#756bb1", alpha = 0.65, size = 2) +
  geom_point(data = filter(e1rm_data, is_flagged),
             aes(fill = flag_type), shape = 21, stroke = 1.4,
             color = "#c0392b", size = 3, alpha = 0.95) +
  facet_wrap(~ lift_label, scales = "free_y", ncol = 3) +
  scale_x_date(date_breaks = "3 months", date_labels = "%b\n'%y") +
  scale_fill_manual(values = flag_colors, guide = "none") +
  labs(
    title    = "Estimated 1RM Over Time (Epley Formula)",
    subtitle = "e1RM = weight × (1 + reps/30) · Shaded band = 95% CI",
    x = NULL, y = "Estimated 1RM (lbs)"
  ) +
  theme_lift

ggsave(file.path(out_dir, "chart3_estimated_1rm.png"), p3,
       width = 12, height = 9, dpi = 150)
message("Saved chart3_estimated_1rm.png")

# ---------------------------------------------------------------------------
# Chart 4: Weekly volume by lift group (stacked area)
# ---------------------------------------------------------------------------
group_map <- c(
  barbell_bench_press = "Push", db_incline_press = "Push", db_flat_bench = "Push",
  dips = "Push", strict_press = "Push", front_squat = "Push",
  row = "Pull", weighted_pull_ups = "Pull", lat_pulldown = "Pull",
  face_pull = "Pull", rear_delt_fly = "Pull", straight_arm_pulldown = "Pull",
  rdl = "Hinge", deadlift = "Hinge", trap_bar_deadlift = "Hinge",
  hip_thrust = "Hinge",
  back_squat = "Squat", leg_press = "Squat", bulgarian_split_squat = "Squat",
  seated_hamstring_curl = "Accessory", triceps_pushdown = "Accessory",
  incline_db_curl = "Accessory", hammer_curl = "Accessory",
  overhead_triceps_extension = "Accessory", lateral_raise = "Accessory",
  glute_kickback = "Accessory", hip_abduction = "Accessory",
  calf_raise = "Accessory", leg_extension = "Accessory",
  hip_adduction = "Accessory"
)

group_levels <- c("Squat", "Hinge", "Push", "Pull", "Accessory")

group_colors <- c(
  Squat     = "#4472C4",
  Hinge     = "#ED7D31",
  Push      = "#A9D18E",
  Pull      = "#5B9BD5",
  Accessory = "#BFBFBF"
)

weekly_vol <- df %>%
  mutate(
    week  = floor_date(date, "week", week_start = 1),
    group = coalesce(group_map[lift_id], "Other")
  ) %>%
  filter(weight > 0, group != "Other") %>%
  group_by(week, group) %>%
  summarise(weekly_vol = sum(volume), .groups = "drop") %>%
  mutate(group = factor(group, levels = group_levels))

total_vol <- weekly_vol %>%
  group_by(week) %>%
  summarise(total = sum(weekly_vol), .groups = "drop")

p4 <- ggplot(weekly_vol, aes(x = week, y = weekly_vol, fill = group)) +
  geom_area(position = "stack", alpha = 0.85) +
  geom_smooth(
    data = total_vol, aes(x = week, y = total),
    inherit.aes = FALSE,
    method = "loess", span = 0.4, se = FALSE,
    color = "gray25", linewidth = 0.9, linetype = "dashed"
  ) +
  scale_fill_manual(values = group_colors) +
  scale_x_date(date_breaks = "2 months", date_labels = "%b '%y") +
  scale_y_continuous(labels = comma) +
  labs(
    title    = "Weekly Training Volume by Muscle Group",
    subtitle = "Volume = sets × reps × weight · Dashed line = LOESS total",
    x = NULL, y = "Weekly Volume (sets × reps × lbs)", fill = NULL
  ) +
  theme_lift +
  guides(fill = guide_legend(nrow = 1))

ggsave(file.path(out_dir, "chart4_weekly_volume.png"), p4,
       width = 12, height = 6, dpi = 150)
message("Saved chart4_weekly_volume.png")

# ---------------------------------------------------------------------------
# Chart 5: Training frequency heatmap (calendar view)
# ---------------------------------------------------------------------------
workout_days <- df %>%
  distinct(date) %>%
  mutate(
    year          = year(date),
    month         = month(date, label = TRUE, abbr = TRUE),
    week_of_month = ceiling(day(date) / 7),
    dow           = wday(date, label = TRUE, abbr = TRUE, week_start = 1)
  )

p5 <- ggplot(workout_days, aes(x = week_of_month, y = fct_rev(dow))) +
  geom_tile(fill = "#4472C4", color = "white", linewidth = 0.5,
            width = 0.88, height = 0.88) +
  facet_grid(year ~ month) +
  scale_x_continuous(breaks = 1:5, labels = paste0("W", 1:5)) +
  labs(title = "Workout Days", x = NULL, y = NULL) +
  theme_minimal(base_size = 9) +
  theme(
    panel.grid   = element_blank(),
    axis.text.x  = element_text(size = 7, color = "gray50"),
    axis.text.y  = element_text(size = 7.5, color = "gray40"),
    strip.text.x = element_text(face = "bold", size = 8),
    strip.text.y = element_text(face = "bold", size = 8),
    plot.title   = element_text(face = "bold", size = 12),
    plot.margin  = margin(10, 12, 8, 12)
  )

ggsave(file.path(out_dir, "chart5_calendar_heatmap.png"), p5,
       width = 14, height = 5, dpi = 150)
message("Saved chart5_calendar_heatmap.png")

# ---------------------------------------------------------------------------
# Chart 6: Outlier review — flagged points in full context
# ---------------------------------------------------------------------------
flagged_lifts <- max_weight_per_session %>%
  filter(is_flagged) %>%
  pull(lift_id) %>%
  unique()

if (length(flagged_lifts) > 0) {
  outlier_data <- max_weight_per_session %>%
    filter(lift_id %in% flagged_lifts) %>%
    group_by(lift_id) %>%
    mutate(
      n_flags     = sum(is_flagged),
      facet_label = paste0(first(lift_label), " (", n_flags, " flag",
                           ifelse(n_flags == 1, "", "s"), ")")
    ) %>%
    ungroup()

  p6 <- ggplot(outlier_data, aes(x = date, y = max_weight)) +
    geom_line(color = "gray80", linewidth = 0.6) +
    geom_point(data = filter(outlier_data, !is_flagged),
               color = "gray60", size = 2, alpha = 0.7) +
    geom_point(data = filter(outlier_data, is_flagged),
               aes(fill = flag_type), shape = 21, size = 4,
               color = "#7b241c", stroke = 1.5, alpha = 0.95) +
    geom_text(data = filter(outlier_data, is_flagged),
              aes(label = paste0(flag_type, "\n", format(date, "%b %d"))),
              size = 2.4, vjust = -0.7, lineheight = 0.9,
              color = "#7b241c", fontface = "italic") +
    geom_text(data = filter(outlier_data, is_flagged),
              aes(label = max_weight),
              size = 2.2, vjust = 1.9, color = "#7b241c") +
    facet_wrap(~ facet_label, scales = "free_y", ncol = 3) +
    scale_x_date(date_breaks = "2 months", date_labels = "%b\n'%y") +
    scale_fill_manual(values = flag_colors, name = "Flag type") +
    labs(
      title    = "Outlier Review — Flagged Entries in Context",
      subtitle = "Gray = normal sessions · Colored dots = flagged (flag type + date + weight)",
      x = NULL, y = "Max Weight (lbs)"
    ) +
    theme_lift +
    theme(strip.background = element_rect(fill = "#fff8e7", color = NA))

  h6 <- max(5, ceiling(length(flagged_lifts) / 3) * 3.5)
  ggsave(file.path(out_dir, "chart6_outlier_review.png"), p6,
         width = 13, height = h6, dpi = 150)
  message("Saved chart6_outlier_review.png")
} else {
  message("No flagged entries — chart6 skipped.")
}

message("\nAll charts saved to: ", out_dir)
