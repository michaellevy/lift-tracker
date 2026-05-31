// Lift definitions
const LIFTS = [
  { id: "barbell_bench_press", name: "Barbell Bench Press", cues: "1\u20132 RIR. Add reps before load. Stable shoulder position." },
  { id: "leg_press", name: "Leg Press", cues: "Depth no deeper than parallel. Smooth tempo." },
  { id: "db_incline_press", name: "Dumbbell Incline Press", cues: "Feet up, power thru whole body." },
  { id: "cable_fly", name: "Cable Fly", cues: "Stretch under control." },
  { id: "row", name: "Row", cues: "" },
  { id: "triceps_pushdown", name: "Triceps Pushdown", cues: "Short rest. Full extension. Lock elbows." },
  { id: "bb_preacher_curl", name: "BB Preacher Curl", cues: "Strict, no shoulder swing. Control eccentric. Tricep flat on pad." },
  { id: "seated_hamstring_curl", name: "Seated Hamstring Curl", cues: "Controlled tempo. No hip shift." },
  { id: "weighted_pull_ups", name: "Weighted Pull-Ups", cues: "Standard pronated grip only — no grip rotation mid-block. Session B: BW for reps. Session C: heavy weighted, top sets first. Double-progress: stay at load until 4x5, then +5lb for 4x3." },
  { id: "db_flat_bench", name: "DB Flat Bench", cues: "Hypertrophy focus. Controlled tempo." },
  { id: "rear_delt_fly", name: "Rear Delt Fly", cues: "Scaps down." },
  { id: "face_pull", name: "Face Pull", cues: "Scaps down. Elbows high. External rotation emphasis." },
  { id: "overhead_triceps_extension", name: "Overhead Triceps Extension", cues: "Control stretch." },
  { id: "hammer_curl", name: "Hammer Curl", cues: "Neutral grip. No torso sway." },
  { id: "dips", name: "Dips", cues: "Stop shy of deep shoulder stretch. Add weight slowly." },
  { id: "lateral_raise_heavy", name: "Lateral Raise (Heavy)", cues: "3x8-10. Controlled but some body english OK. Arms 15\u00b0 forward; pull out not up. Focus on mechanical tension." },
  { id: "lateral_raise", name: "Lateral Raise (Light)", cues: "3x12-15. Strict form, slow eccentric, pause at top. Arms 15\u00b0 forward; pull out not up. No shrugging." },
  { id: "hip_abduction", name: "Hip Abduction", cues: "Slight forward lean. Controlled reps." },
  { id: "glute_kickback", name: "Glute Kickback", cues: "Height 4. Feel glute to hamstring on push. No lumbar extension." },
  { id: "pallof_press", name: "Pallof Press", cues: "Anti-rotation focus. Neutral pelvis." },
  { id: "cable_rotation", name: "Cable Rotation", cues: "Explosive but controlled. No lumbar rotation." },
  // Retired — kept here so prior history is browsable. Not in any session.
  { id: "box_jumps", name: "Box Jumps (retired)", cues: "Retired." },
  { id: "trap_bar_deadlift", name: "Trap Bar Deadlift (retired)", cues: "Retired." },
  { id: "incline_db_curl", name: "Incline DB Curl (retired)", cues: "Retired — moved off due to elbow stress." },
];

// Session definitions
// rx format: "sets x reps", "sets-sets x reps-reps", "alt: 3x5, 4x5-6", or with "/side"
// The app auto-fills the form with the high end of each range.
const SESSIONS = [
  {
    id: "session_a",
    name: "Session A",
    lifts: [
      { liftId: "barbell_bench_press", rx: "alt: 3x5, 4x5-6" },
      { liftId: "row", rx: "3-4 x 8-12" },
      {
        choose: [
          { liftId: "db_incline_press", rx: "3-4 x 8-12" },
          { liftId: "cable_fly", rx: "3 x 12-15" }
        ],
        note: "4-week rotation"
      },
      { liftId: "triceps_pushdown", rx: "2-4 x 10-15" },
      { liftId: "bb_preacher_curl", rx: "2-3 x 8-12" },
      { liftId: "lateral_raise_heavy", rx: "3 x 8-10" },
    ]
  },
  {
    id: "session_b",
    name: "Session B",
    lifts: [
      { liftId: "leg_press", rx: "2-3 x 8-10" },
      { liftId: "db_flat_bench", rx: "3-4 x 8-12" },
      { liftId: "weighted_pull_ups", rx: "4 x 6-10 BW" },
      { liftId: "seated_hamstring_curl", rx: "2-3 x 10-15" },
      {
        choose: [
          { liftId: "rear_delt_fly", rx: "3 x 12-15" },
          { liftId: "face_pull", rx: "3 x 12-15" }
        ]
      },
      { liftId: "overhead_triceps_extension", rx: "2-3 x 10-15" },
      { liftId: "hammer_curl", rx: "2-3 x 10-15" },
      { liftId: "lateral_raise", rx: "3 x 12-15" },
    ]
  },
  {
    id: "session_c",
    name: "Session C",
    lifts: [
      { liftId: "weighted_pull_ups", rx: "4 x 4-5" },
      { liftId: "dips", rx: "3-4 x 6-10" },
      { liftId: "lateral_raise", rx: "3 x 12-15" },
      { liftId: "hip_abduction", rx: "2-3 x 12-20" },
      { liftId: "glute_kickback", rx: "2-3 x 12-15" },
      { liftId: "pallof_press", rx: "2-3 x 10-15/side" },
      { liftId: "cable_rotation", rx: "3 x 5-8/side" },
    ]
  },
];
