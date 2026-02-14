// Lift definitions
const LIFTS = [
  { id: "box_jumps", name: "Box Jumps", cues: "Jump up, step down. Keep 18\u201322\u2033. Max intent, full reset." },
  { id: "barbell_bench_press", name: "Barbell Bench Press", cues: "1\u20132 RIR. Add reps before load. Stable shoulder position." },
  { id: "leg_press", name: "Leg Press", cues: "Depth no deeper than parallel. Smooth tempo." },
  { id: "db_incline_press", name: "Dumbbell Incline Press", cues: "Feet up, power thru whole body." },
  { id: "cable_fly", name: "Cable Fly", cues: "Stretch under control." },
  { id: "row", name: "Row", cues: "" },
  { id: "triceps_pushdown", name: "Triceps Pushdown", cues: "Short rest. Full extension. Lock elbows." },
  { id: "incline_db_curl", name: "Incline DB Curl", cues: "Full stretch. No swing." },
  { id: "trap_bar_deadlift", name: "Trap Bar Deadlift", cues: "RIR 2. No grinding. Abort if hip awareness." },
  { id: "seated_hamstring_curl", name: "Seated Hamstring Curl", cues: "Controlled tempo. No hip shift." },
  { id: "weighted_pull_ups", name: "Weighted Pull-Ups", cues: "Shoulder-width or neutral grip. Add weight gradually." },
  { id: "db_flat_bench", name: "DB Flat Bench", cues: "Hypertrophy focus. Controlled tempo." },
  { id: "rear_delt_fly", name: "Rear Delt Fly", cues: "Scaps down." },
  { id: "face_pull", name: "Face Pull", cues: "Scaps down. Elbows high. External rotation emphasis." },
  { id: "overhead_triceps_extension", name: "Overhead Triceps Extension", cues: "Control stretch." },
  { id: "hammer_curl", name: "Hammer Curl", cues: "Neutral grip. No torso sway." },
  { id: "dips", name: "Dips", cues: "Stop shy of deep shoulder stretch. Add weight slowly." },
  { id: "straight_arm_pulldown", name: "Straight Arm Pulldown", cues: "Minimal elbow bend." },
  { id: "lateral_raise", name: "Lateral Raise", cues: "Soft elbows. Avoid shrugging. Arms 15\u00b0 forward; pull out not up." },
  { id: "hip_abduction", name: "Hip Abduction", cues: "Slight forward lean. Controlled reps." },
  { id: "glute_kickback", name: "Glute Kickback", cues: "Height 4. Feel glute to hamstring on push. No lumbar extension." },
  { id: "pallof_press", name: "Pallof Press", cues: "Anti-rotation focus. Neutral pelvis." },
  { id: "cable_rotation", name: "Cable Rotation", cues: "Explosive but controlled. No lumbar rotation." },
];

// Session definitions
// rx format: "sets x reps", "sets-sets x reps-reps", "alt: 3x5, 4x5-6", or with "/side"
// The app auto-fills the form with the high end of each range.
const SESSIONS = [
  {
    id: "session_a",
    name: "Session A",
    lifts: [
      { liftId: "box_jumps", rx: "4-6 x 2-3" },
      { liftId: "barbell_bench_press", rx: "alt: 3x5, 4x5-6" },
      { liftId: "leg_press", rx: "2-3 x 8-10" },
      {
        choose: [
          { liftId: "db_incline_press", rx: "3-4 x 8-12" },
          { liftId: "cable_fly", rx: "3 x 12-15" }
        ],
        note: "4-week rotation"
      },
      { liftId: "row", rx: "3-4 x 8-12" },
      { liftId: "triceps_pushdown", rx: "2-4 x 10-15" },
      { liftId: "incline_db_curl", rx: "2-4 x 10-15" },
    ]
  },
  {
    id: "session_b",
    name: "Session B",
    lifts: [
      { liftId: "trap_bar_deadlift", rx: "3 x 5" },
      { liftId: "seated_hamstring_curl", rx: "2-3 x 10-15" },
      { liftId: "weighted_pull_ups", rx: "4-5 x 4-8" },
      { liftId: "db_flat_bench", rx: "3-4 x 8-12" },
      {
        choose: [
          { liftId: "rear_delt_fly", rx: "3 x 12-15" },
          { liftId: "face_pull", rx: "3 x 12-15" }
        ]
      },
      { liftId: "overhead_triceps_extension", rx: "2-3 x 10-15" },
      { liftId: "hammer_curl", rx: "2-3 x 10-15" },
    ]
  },
  {
    id: "session_c",
    name: "Session C",
    lifts: [
      { liftId: "dips", rx: "3-4 x 6-10" },
      { liftId: "straight_arm_pulldown", rx: "3 x 12-15" },
      { liftId: "lateral_raise", rx: "3 x 12-15" },
      { liftId: "hip_abduction", rx: "2-3 x 12-20" },
      { liftId: "glute_kickback", rx: "2-3 x 12-15" },
      { liftId: "pallof_press", rx: "2-3 x 10-15/side" },
      { liftId: "cable_rotation", rx: "3 x 5-8/side" },
    ]
  },
];
