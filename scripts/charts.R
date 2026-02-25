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
  trap_bar_deadlift          = "Trap Bar Deadlift",
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
  straight_arm_pulldown      = "Straight Arm Pulldown",
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
    # First flag keyword only (e.g. "weight_drop" from "weight_drop:145→50")
    flag_type  = ifelse(is_flagged,
                        sub(":.*", "", sub(";.*", "", trimws(flag))),
                        "ok")
  )

# Colour palette for flag types
flag_colors <- c(
  weight_drop         = "#e74c3c",
  weight_jump_up      = "#e67e22",
  zero_weight_barbell = "#8e44ad",
  high_volume         = "#27ae60",
  ok                  = "#2c7bb6"
)

out_dir <- script_dir

# ---------------------------------------------------------------------------
# Chart 1: Weight over time — current program lifts
# ---------------------------------------------------------------------------
curr_data <- max_weight_per_session %>%
  filter(in_current, !lift_id %in% c("box_jumps", "pallof_press", "cable_rotation"))

p1 <- ggplot(curr_data, aes(x = date, y = max_weight)) +
  # Normal points
  geom_point(data = filter(curr_data, !is_flagged),
             aes(size = total_volume), alpha = 0.65, color = "#2c7bb6") +
  # Flagged points — orange fill, red stroke
  geom_point(data = filter(curr_data, is_flagged),
             aes(size = total_volume, fill = flag_type),
             shape = 21, stroke = 1.4, color = "#c0392b", alpha = 0.95) +
  # Flag label beneath flagged point
  geom_text(data = filter(curr_data, is_flagged),
            aes(label = flag_type), size = 2.0, vjust = 2.2,
            color = "#c0392b", fontface = "italic") +
  geom_smooth(method = "loess", span = 0.6, se = FALSE,
              color = "#d7191c", linewidth = 0.8, na.rm = TRUE) +
  facet_wrap(~ lift_label, scales = "free_y", ncol = 4) +
  scale_x_date(date_breaks = "3 months", date_labels = "%b\n%Y") +
  scale_size_continuous(range = c(1, 5),
                        guide = guide_legend(title = "Volume\n(s×r×w)")) +
  scale_fill_manual(values = flag_colors, guide = "none") +
  labs(
    title    = "Current Program — Weight Over Time",
    subtitle = "Blue = normal · Outlined = flagged (label shows flag type) · Red line = LOESS trend.",
    x = NULL, y = "Weight (lbs)"
  ) +
  theme_bw(base_size = 10) +
  theme(
    strip.background = element_rect(fill = "#f0f0f0"),
    panel.grid.minor = element_blank(),
    plot.title       = element_text(face = "bold", size = 13),
    legend.position  = "bottom"
  )

ggsave(file.path(out_dir, "chart1_current_program.png"), p1,
       width = 14, height = 12, dpi = 150)
message("Saved chart1_current_program.png")

# ---------------------------------------------------------------------------
# Chart 2: Weight over time — compound lifts
# ---------------------------------------------------------------------------
hist_data <- max_weight_per_session %>%
  filter(lift_id %in% c("back_squat", "deadlift", "rdl",
                         "strict_press", "front_squat",
                         "barbell_bench_press", "trap_bar_deadlift",
                         "hip_thrust", "bulgarian_split_squat",
                         "lat_pulldown", "weighted_pull_ups", "dips"))

p2 <- ggplot(hist_data, aes(x = date, y = max_weight,
                              color = lift_label, group = lift_label)) +
  geom_point(data = filter(hist_data, !is_flagged), alpha = 0.6, size = 2) +
  geom_point(data = filter(hist_data, is_flagged),
             size = 3.5, shape = 24, fill = "#e74c3c", color = "#7b241c",
             stroke = 1.2, alpha = 0.95) +
  geom_line(alpha = 0.35, linewidth = 0.5) +
  geom_smooth(method = "loess", span = 0.7, se = FALSE,
              linewidth = 1.2, na.rm = TRUE) +
  scale_x_date(date_breaks = "2 months", date_labels = "%b '%y") +
  scale_color_brewer(palette = "Paired") +
  labs(
    title    = "Compound / Featured Lifts — Weight Over Time",
    subtitle = "Red triangles = flagged entries. LOESS trend per lift.",
    x = NULL, y = "Weight (lbs)", color = NULL
  ) +
  theme_bw(base_size = 11) +
  theme(
    legend.position  = "bottom",
    legend.key.size  = unit(0.8, "lines"),
    panel.grid.minor = element_blank(),
    plot.title       = element_text(face = "bold", size = 13)
  ) +
  guides(color = guide_legend(nrow = 3))

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
    best_e1rm  = max(e1rm),
    flag       = paste(unique(flag[flag != ""]), collapse = "; "),
    .groups    = "drop"
  ) %>%
  mutate(
    is_flagged = flag != "",
    flag_type  = ifelse(is_flagged,
                        sub(":.*", "", sub(";.*", "", trimws(flag))),
                        "ok")
  )

p3 <- ggplot(e1rm_data, aes(x = date, y = best_e1rm)) +
  geom_point(data = filter(e1rm_data, !is_flagged),
             color = "#756bb1", alpha = 0.65, size = 2) +
  geom_point(data = filter(e1rm_data, is_flagged),
             aes(fill = flag_type), shape = 21, stroke = 1.4,
             color = "#c0392b", size = 3, alpha = 0.95) +
  geom_text(data = filter(e1rm_data, is_flagged),
            aes(label = flag_type), size = 2.0, vjust = 2.4,
            color = "#c0392b", fontface = "italic") +
  geom_smooth(method = "loess", span = 0.6, se = TRUE, fill = "#cbc9e2",
              color = "#54278f", linewidth = 0.9, na.rm = TRUE) +
  facet_wrap(~ lift_label, scales = "free_y", ncol = 3) +
  scale_x_date(date_breaks = "3 months", date_labels = "%b\n%Y") +
  scale_fill_manual(values = flag_colors, guide = "none") +
  labs(
    title    = "Estimated 1RM Over Time (Epley Formula)",
    subtitle = "e1RM = weight × (1 + reps/30). Outlined points = flagged. Shaded = 95% CI.",
    x = NULL, y = "Estimated 1RM (lbs)"
  ) +
  theme_bw(base_size = 10) +
  theme(
    strip.background = element_rect(fill = "#f0f0f0"),
    panel.grid.minor = element_blank(),
    plot.title       = element_text(face = "bold", size = 13)
  )

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
  back_squat = "Squat", leg_press = "Squat",
  bulgarian_split_squat = "Squat",
  seated_hamstring_curl = "Accessory", triceps_pushdown = "Accessory",
  incline_db_curl = "Accessory", hammer_curl = "Accessory",
  overhead_triceps_extension = "Accessory", lateral_raise = "Accessory",
  glute_kickback = "Accessory", hip_abduction = "Accessory",
  calf_raise = "Accessory", leg_extension = "Accessory",
  hip_adduction = "Accessory"
)

weekly_vol <- df %>%
  mutate(
    week  = floor_date(date, "week", week_start = 1),
    group = coalesce(group_map[lift_id], "Other")
  ) %>%
  filter(weight > 0, group != "Other") %>%
  group_by(week, group) %>%
  summarise(weekly_vol = sum(volume), .groups = "drop")

group_colors <- c(
  Push = "#e41a1c", Pull = "#377eb8", Hinge = "#ff7f00",
  Squat = "#4daf4a", Accessory = "#984ea3"
)

p4 <- ggplot(weekly_vol, aes(x = week, y = weekly_vol, fill = group)) +
  geom_area(alpha = 0.8, position = "stack") +
  scale_fill_manual(values = group_colors) +
  scale_x_date(date_breaks = "2 months", date_labels = "%b '%y") +
  scale_y_continuous(labels = comma) +
  labs(
    title    = "Weekly Training Volume by Muscle Group",
    subtitle = "Volume = sets × reps × weight, stacked by group.",
    x = NULL, y = "Weekly Volume (sets × reps × lbs)", fill = "Group"
  ) +
  theme_bw(base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    legend.position  = "bottom",
    plot.title       = element_text(face = "bold", size = 13)
  )

ggsave(file.path(out_dir, "chart4_weekly_volume.png"), p4,
       width = 12, height = 6, dpi = 150)
message("Saved chart4_weekly_volume.png")

# ---------------------------------------------------------------------------
# Chart 5: Training frequency heatmap (calendar view)
# ---------------------------------------------------------------------------
workout_days <- df %>%
  distinct(date) %>%
  mutate(
    year         = year(date),
    month        = month(date, label = TRUE, abbr = TRUE),
    week_of_month = ceiling(day(date) / 7),
    dow          = wday(date, label = TRUE, abbr = TRUE, week_start = 1)
  )

p5 <- ggplot(workout_days, aes(x = week_of_month, y = fct_rev(dow))) +
  geom_tile(fill = "#2c7bb6", color = "white", linewidth = 0.4,
            width = 0.9, height = 0.9) +
  facet_grid(year ~ month) +
  scale_x_continuous(breaks = 1:5, labels = paste0("W", 1:5)) +
  labs(
    title    = "Workout Days (Calendar Heatmap)",
    subtitle = "Each tile = one training session.",
    x = NULL, y = NULL
  ) +
  theme_bw(base_size = 9) +
  theme(
    panel.grid   = element_blank(),
    axis.text.x  = element_text(size = 7),
    strip.text.x = element_text(size = 8),
    strip.text.y = element_text(size = 8),
    plot.title   = element_text(face = "bold", size = 12)
  )

ggsave(file.path(out_dir, "chart5_calendar_heatmap.png"), p5,
       width = 14, height = 5, dpi = 150)
message("Saved chart5_calendar_heatmap.png")

# ---------------------------------------------------------------------------
# Chart 6: Outlier review — flagged points in full context
# Show every flagged lift's complete history; flag points highlighted in red.
# ---------------------------------------------------------------------------
flagged_lifts <- max_weight_per_session %>%
  filter(is_flagged) %>%
  pull(lift_id) %>%
  unique()

if (length(flagged_lifts) > 0) {
  outlier_data <- max_weight_per_session %>%
    filter(lift_id %in% flagged_lifts) %>%
    # Richer facet label: lift name + flag count
    group_by(lift_id) %>%
    mutate(
      n_flags    = sum(is_flagged),
      facet_label = paste0(first(lift_label), " (", n_flags, " flag",
                           ifelse(n_flags == 1, "", "s"), ")")
    ) %>%
    ungroup()

  p6 <- ggplot(outlier_data, aes(x = date, y = max_weight)) +
    # Full history in gray
    geom_line(color = "gray70", linewidth = 0.6) +
    geom_point(data = filter(outlier_data, !is_flagged),
               color = "gray55", size = 2.2, alpha = 0.75) +
    # Flagged points: filled red circle, no size jitter
    geom_point(data = filter(outlier_data, is_flagged),
               aes(fill = flag_type), shape = 21, size = 4,
               color = "#7b241c", stroke = 1.5, alpha = 0.95) +
    # Flag type label above point
    geom_text(data = filter(outlier_data, is_flagged),
              aes(label = paste0(flag_type, "\n", format(date, "%b %d"))),
              size = 2.3, vjust = -0.8, lineheight = 0.9,
              color = "#7b241c", fontface = "italic") +
    # Weight label on flagged point
    geom_text(data = filter(outlier_data, is_flagged),
              aes(label = max_weight),
              size = 2.1, vjust = 1.9, color = "#7b241c") +
    facet_wrap(~ facet_label, scales = "free_y", ncol = 3) +
    scale_x_date(date_breaks = "2 months", date_labels = "%b\n%y") +
    scale_fill_manual(values = flag_colors, name = "Flag type") +
    labs(
      title    = "Outlier Review — Flagged Entries in Context",
      subtitle = paste0(
        "Gray = normal sessions · Colored dots = flagged (label = flag type + date + weight).\n",
        "Review each to decide whether to delete, override, or keep."
      ),
      x = NULL, y = "Max Weight (lbs)"
    ) +
    theme_bw(base_size = 10) +
    theme(
      strip.background = element_rect(fill = "#fff3cd"),
      strip.text       = element_text(face = "bold", size = 8.5),
      panel.grid.minor = element_blank(),
      plot.title       = element_text(face = "bold", size = 13),
      plot.subtitle    = element_text(size = 9, color = "gray40"),
      legend.position  = "bottom"
    )

  h6 <- max(5, ceiling(length(flagged_lifts) / 3) * 3.5)
  ggsave(file.path(out_dir, "chart6_outlier_review.png"), p6,
         width = 13, height = h6, dpi = 150)
  message("Saved chart6_outlier_review.png")
} else {
  message("No flagged entries — chart6 skipped.")
}

message("\nAll charts saved to: ", out_dir)
