"""
Parse all YYYY-MM sheets and write a preview to a new Google Sheet tab.

Columns: date | lift_id | lift_name | sets | reps | weight | notes | flag | source_sheet | raw_text

Run this first to review before importing to Firestore.
"""

import os, re, json, csv
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Strava ground-truth dates
# ---------------------------------------------------------------------------

STRAVA_JSON = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "strava-bodycomp", "strava_activities.json")
)
_STRAVA_STRENGTH_TYPES = {"WeightTraining", "Crossfit"}


def load_strava_dates():
    """Return set of dates with WeightTraining/Crossfit Strava activities."""
    if not os.path.exists(STRAVA_JSON):
        return set()
    with open(STRAVA_JSON) as f:
        data = json.load(f)
    return {
        date.fromisoformat(a["start_date_local"][:10])
        for a in data.get("activities", [])
        if a.get("sport_type") in _STRAVA_STRENGTH_TYPES or a.get("type") in _STRAVA_STRENGTH_TYPES
    }


def snap_to_strava(d, strava_dates, tol=4):
    """Return nearest Strava date within tol days (prefer forward), or d unchanged."""
    if not strava_dates or d in strava_dates:
        return d
    for delta in range(1, tol + 1):
        if d + timedelta(days=delta) in strava_dates:
            return d + timedelta(days=delta)
        if d - timedelta(days=delta) in strava_dates:
            return d - timedelta(days=delta)
    return d


# Module-level Strava dates (set by main() before parsing)
_strava_dates: set = set()


def _strava_window(start, end):
    """Return sorted list of Strava workout dates in [start, end)."""
    return sorted(d for d in _strava_dates if start <= d < end)


from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SPREADSHEET_ID = "1BpjoT3mXofJem4JMQtbbi3c8O35ftRAQ4ley2zSgcEQ"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE  = os.path.join(os.path.dirname(__file__), "token.json")
PREVIEW_SHEET_NAME = "import-preview"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)


# ---------------------------------------------------------------------------
# Lift name → ID mapping
# ---------------------------------------------------------------------------

LIFT_MAP = {
    # Current app lifts
    "box jumps":                        "box_jumps",
    "box jump":                         "box_jumps",
    "barbell bench press":              "barbell_bench_press",
    "bench press":                      "barbell_bench_press",
    "bench":                            "barbell_bench_press",
    "leg press":                        "leg_press",
    "leg press (narrow stance)":        "leg_press",
    "dumbbell incline press":           "db_incline_press",
    "incline dumbbell press":           "db_incline_press",
    "inclined db press":                "db_incline_press",
    "db incline press":                 "db_incline_press",
    "cable fly":                        "cable_fly",
    "row":                              "row",
    "barbell row":                      "row",
    "chest-supported row (medium grip)":"row",
    "chest supported db row":           "row",
    "dumbbell row":                     "row",
    "db row":                           "row",
    "db rows":                          "row",
    "triceps pushdown":                 "triceps_pushdown",
    "rope pushdown":                    "triceps_pushdown",
    "band pushdowns":                   "triceps_pushdown",
    "incline db curl":                  "incline_db_curl",
    "incline curl":                     "incline_db_curl",
    "trap-bar deadlift":                "trap_bar_deadlift",
    "trap bar deadlift":                "trap_bar_deadlift",
    "trap bar dl":                      "trap_bar_deadlift",
    "dl trap":                          "trap_bar_deadlift",
    "seated hamstring curl":            "seated_hamstring_curl",
    "hamstring curl (machine)":         "seated_hamstring_curl",
    "hamstring curl":                   "seated_hamstring_curl",
    "weighted pull-ups":                "weighted_pull_ups",
    "weighted pull-up":                 "weighted_pull_ups",
    "weighted pullup":                  "weighted_pull_ups",
    "pull-up (neutral or supinated)":   "weighted_pull_ups",
    "pullups":                          "weighted_pull_ups",
    "pull-ups":                         "weighted_pull_ups",
    "strict pull-ups":                  "weighted_pull_ups",
    "chin-up":                          "weighted_pull_ups",
    "angled chin ups":                  "weighted_pull_ups",
    "db flat bench":                    "db_flat_bench",
    "dumbbell bench press (flat or 15\u00b0 incline)": "db_flat_bench",
    "dumbbell bench press":             "db_flat_bench",
    "rear delt fly":                    "rear_delt_fly",
    "rear-delt fly (light warm-up set or finisher)": "rear_delt_fly",
    "face pull":                        "face_pull",
    "face pull / reverse pec deck":     "face_pull",
    "face pulls":                       "face_pull",
    "face pull warmup":                 "face_pull",
    "overhead triceps extension":       "overhead_triceps_extension",
    "oh cable extension":               "overhead_triceps_extension",
    "overhead cable extension":         "overhead_triceps_extension",
    "hammer curl":                      "hammer_curl",
    "dips":                             "dips",
    "weighted dip":                     "dips",
    "weighted dips":                    "dips",
    "bar dips":                         "dips",
    "ring dips":                        "dips",
    "straight arm pulldown":            "straight_arm_pulldown",
    "straight-arm pulldown":            "straight_arm_pulldown",
    "lateral raise":                    "lateral_raise",
    "lateral raise (machine or cable)": "lateral_raise",
    "lateral raises":                   "lateral_raise",
    "hip abduction":                    "hip_abduction",
    "hip ad push out":                  "hip_abduction",
    "glute kickback":                   "glute_kickback",
    "glute kickback or single-leg hip thrust (alternate weekly)": "glute_kickback",
    "glute extension":                  "glute_kickback",
    "pallof press":                     "pallof_press",
    "pallof press (warm-up)":           "pallof_press",
    "cable rotation":                   "cable_rotation",

    # 2025-09-08 sheet lifts
    "back squat to 18\" box":           "back_squat",
    "leg extension":                    "leg_extension",
    "pull-up (weighted if possible)":   "weighted_pull_ups",
    "chest-supported row":              "row",
    "band/rope pushdowns":              "triceps_pushdown",
    "hammer curl or alt curl":          "hammer_curl",
    "glute machine kickback":           "glute_kickback",
    "adductor machine or copenhagen plank": "hip_adduction",
    "step-up":                          "step_ups",
    "biceps curls (any variation)":     "incline_db_curl",

    # Historical lifts (new IDs)
    "back squat":                       "back_squat",
    "box back squat (16\u201318\")":    "back_squat",
    "box back squat":                   "back_squat",
    "deadlift":                         "deadlift",
    "strict press":                     "strict_press",
    "overhead press":                   "strict_press",
    "front squat":                      "front_squat",
    "romanian deadlift":                "rdl",
    "rdl":                              "rdl",
    "barbell hip thrust":               "hip_thrust",
    "hip thrust (15\" box)":            "hip_thrust",
    "hip thrust":                       "hip_thrust",
    "bulgarian split squat":            "bulgarian_split_squat",
    "lat pulldown (underhand)":         "lat_pulldown",
    "lat pulldown":                     "lat_pulldown",
    "single-leg rdl":                   "single_leg_rdl",
    "farmer\u2019s carries":            "farmers_carry",
    "farmer's carries":                 "farmers_carry",
    "step-ups":                         "step_ups",
    "db step-ups":                      "step_ups",
    "walking lunge":                    "walking_lunge",
    "standing calf raise":              "calf_raise",
    "seated calf raise":                "calf_raise",
    "hanging leg raise":                "hanging_leg_raise",
    "hanging leg raises":               "hanging_leg_raise",
    "hip ab push in":                   "hip_adduction",
}

CURRENT_LIFT_NAMES = {
    "box_jumps": "Box Jumps",
    "barbell_bench_press": "Barbell Bench Press",
    "leg_press": "Leg Press",
    "db_incline_press": "Dumbbell Incline Press",
    "cable_fly": "Cable Fly",
    "row": "Row",
    "triceps_pushdown": "Triceps Pushdown",
    "incline_db_curl": "Incline DB Curl",
    "trap_bar_deadlift": "Trap Bar Deadlift",
    "seated_hamstring_curl": "Seated Hamstring Curl",
    "weighted_pull_ups": "Weighted Pull-Ups",
    "db_flat_bench": "DB Flat Bench",
    "rear_delt_fly": "Rear Delt Fly",
    "face_pull": "Face Pull",
    "overhead_triceps_extension": "Overhead Triceps Extension",
    "hammer_curl": "Hammer Curl",
    "dips": "Dips",
    "straight_arm_pulldown": "Straight Arm Pulldown",
    "lateral_raise": "Lateral Raise",
    "hip_abduction": "Hip Abduction",
    "glute_kickback": "Glute Kickback",
    "pallof_press": "Pallof Press",
    "cable_rotation": "Cable Rotation",
}

HISTORICAL_LIFT_NAMES = {
    "back_squat": "Back Squat",
    "deadlift": "Deadlift",
    "strict_press": "Strict Press",
    "front_squat": "Front Squat",
    "rdl": "Romanian Deadlift",
    "hip_thrust": "Hip Thrust",
    "bulgarian_split_squat": "Bulgarian Split Squat",
    "lat_pulldown": "Lat Pulldown",
    "single_leg_rdl": "Single-Leg RDL",
    "farmers_carry": "Farmer's Carries",
    "step_ups": "Step-Ups",
    "walking_lunge": "Walking Lunge",
    "calf_raise": "Calf Raise",
    "hanging_leg_raise": "Hanging Leg Raise",
    "hip_adduction": "Hip Adduction",
    "leg_extension": "Leg Extension",
}


def resolve_lift(name: str):
    """Return (lift_id, display_name) or (None, None)."""
    key = name.strip().lower()
    key = re.sub(r"\s+[–—]\s+.*$", "", key).strip()
    lift_id = LIFT_MAP.get(key)
    if lift_id is None:
        return None, None
    display = CURRENT_LIFT_NAMES.get(lift_id) or HISTORICAL_LIFT_NAMES.get(lift_id) or lift_id
    return lift_id, display


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_weight(s: str):
    """Return float weight, 0.0 for bodyweight/band, None if can't determine."""
    s = _preprocess_db_notation(s.strip())
    s = s.lower()
    if not s:
        return None
    NON_NUMERIC = {"band","bands","bodyweight","bw","light","moderate","mod","medium",
                   "heavy","seconds","rower","jump","rope","bar","pull-up bar","box",
                   "dbs","light-mod","rpe","--","grip-focused","slight","target",
                   "moderate-heavy","progressed load","progressed","finish strong"}
    if s in NON_NUMERIC or s.startswith("bw") or s.startswith("bodyweight"):
        return 0.0
    if any(w in s for w in ("band", "bodyweight", "rpe")):
        return 0.0

    # Strip any NxM (or NxM-M) patterns — they're sets/reps, not weights.
    # Then find the remaining numeric value, which is the actual weight.
    s_no_scheme = re.sub(r"\d+\s*[xX×]\s*\d+(?:\s*[-–]\s*\d+)?", "", s).strip()
    s_to_search = s_no_scheme if s_no_scheme.strip() else None
    if s_to_search is None:
        return None  # only had NxM, no separate weight

    s2 = re.sub(r"\s*(lb|lbs|#|kg)\b", " ", s_to_search).strip()
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s2)]
    if nums:
        # Prefer the largest plausible weight
        plausible = [n for n in nums if 0 < n <= 800]
        if plausible:
            return max(plausible)
        return nums[0]
    return 0.0


def parse_sets_reps_scheme(scheme: str):
    """Parse '5x5', '4x5-6', '3x8-10', '2x10/side', etc. Returns (sets, reps) maxes."""
    if not scheme:
        return None, None
    scheme = re.sub(r"/side", "", scheme, flags=re.I)
    m = re.match(
        r"(\d+)(?:\s*[-–]\s*(\d+))?\s*[xX×]\s*(\d+)(?:\s*[-–]\s*(\d+))?",
        scheme.strip()
    )
    if not m:
        return None, None
    return int(m.group(2) or m.group(1)), int(m.group(4) or m.group(3))


def _preprocess_db_notation(s: str) -> str:
    """Convert 'Ns' per-hand dumbbell notation to just 'N' (e.g., '50s 3x10' → '50 3x10').
    Also strip uncertain '?' after a number (e.g., '215? 5x5' → '215 5x5').
    Lookahead uses \\W so '20s.' (period after s) is also caught."""
    s = re.sub(r"(\d+)s(?=\W|$)", r"\1", s)
    s = re.sub(r"(\d+)\?(?=\s|$)", r"\1", s)
    return s


def is_ditto(cell: str) -> bool:
    """True if cell is a lone ditto/quote mark meaning 'same as before'."""
    c = cell.strip()
    return c in ('"', '\u201c', '\u201d', '\u2019')


def ditto_suffix(cell: str):
    """If cell starts with a ditto mark and has extra text, return the suffix."""
    c = cell.strip()
    for quote in ('"', '\u201c', '\u201d'):
        if c.startswith(quote) and len(c) > 1:
            return c[1:].strip()
    return None


def extract_performance(notes: str, planned_sets, planned_reps, planned_weight):
    """
    Returns (sets, reps, weight, notes_clean) from a cell.
    Falls back to planned values when the note just confirms execution.
    Returns (None,...) if the lift was clearly not done (empty cell).
    """
    notes = (notes or "").strip()
    if not notes:
        return None, None, None, ""

    notes = _preprocess_db_notation(notes)  # "50s" → "50"

    s = planned_sets
    r = planned_reps
    w = planned_weight

    # "nope: R1R2R3" or "W NxM nope N1 N2 N3" — actual per-set rep counts
    # Digits concatenated like "776" → [7,7,6]; space-separated "15 15 13" → [15,15,13].
    nope_m = re.search(r"\bnope[:\s]+(\S.*)", notes, re.I)
    if nope_m:
        after_nope = nope_m.group(1)
        raw_reps = re.findall(r"\d+", after_nope)
        expanded = []
        for rn in raw_reps:
            val = int(rn)
            # Concatenated single-digit reps (e.g. "776" → 7,7,6)
            if val > 99 and len(rn) >= 3 and all(int(d) >= 1 for d in rn):
                expanded.extend(int(d) for d in rn)
            else:
                expanded.append(val)
        if expanded and all(rep <= 30 for rep in expanded):
            n_sets = len(expanded)
            min_reps = min(expanded)
            before_nope = notes[:nope_m.start()].strip()
            # Extract weight from before "nope" (pattern: W NxM)
            wm = re.search(r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|#|kg)?\s+\d+[xX×]", before_nope)
            nw = float(wm.group(1)) if wm and float(wm.group(1)) >= 10 else (w or 0.0)
            return n_sets, min_reps, nw, notes

    # "W# N/N/M" — weight then slash-separated per-set rep counts (e.g. "25# 4/4/2")
    slash_m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:lb|lbs|#|kg)?\s+((?:\d+/)+\d+)", notes)
    if slash_m:
        nw = float(slash_m.group(1))
        rep_counts = [int(x) for x in slash_m.group(2).split("/")]
        if nw >= 10 and all(1 <= rc <= 30 for rc in rep_counts):
            return len(rep_counts), min(rep_counts), nw, notes

    # "N×M @W" or "N×M W" — full match
    full = re.search(r"(\d+)\s*[xX×]\s*(\d+)(?:\s*@\s*|\s+)(\d+(?:\.\d+)?)", notes)
    if full:
        ns, nr, nw = int(full.group(1)), int(full.group(2)), float(full.group(3))
        # Sanity: if "reps" looks like a weight (>50), it's probably "N reps @ W lbs"
        if nr > 50:
            return 1, ns, nw, notes
        return ns, nr, nw, notes

    # "W N×M" — weight first (e.g. "135 3x5" or "50# dbs 3x15")
    wfirst = re.search(r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|#|kg)?(?:\s+\w+)?\s+(\d+)[xX×](\d+)", notes)
    if wfirst:
        nw, ns, nr = float(wfirst.group(1)), int(wfirst.group(2)), int(wfirst.group(3))
        if ns <= 15 and nr <= 40 and nw > ns and nw > nr:  # plausibility check
            return ns, nr, nw, notes

    # "N×M" alone — look for a weight before or after it
    scheme = re.search(r"(\d+)[xX×](\d+)", notes)
    if scheme:
        ns, nr = int(scheme.group(1)), int(scheme.group(2))
        # If reps > 50, this is likely "N reps @ W" — treat second as weight
        if nr > 50:
            return 1, ns, float(nr), notes
        # Look for weight in the text before the match
        before = notes[:scheme.start()]
        wm_before = re.search(r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|#|kg)?(?:\s+\w+)?\s*$", before)
        if wm_before:
            nw = float(wm_before.group(1))
            if nw > 20:
                return ns, nr, nw, notes
        # Look for weight after the match
        after = notes[scheme.end():]
        wm_after = re.search(r"\b(\d+(?:\.\d+)?)\b", after)
        nw = float(wm_after.group(1)) if wm_after and float(wm_after.group(1)) > 20 else (w or 0.0)
        return ns, nr, nw, notes

    # "xxxxx" / "iiiii" — x or i count = sets done at plan
    xi = re.match(r"^([xi]+)", notes, re.I)
    if xi:
        n_sets = len(xi.group(1))
        return n_sets, (r or 0), (w or 0.0), notes

    # "Nrm test: W" or "build to Nrm" patterns
    rm_test = re.search(r"(\d+)\s*rm(?:\s+test)?[:\s,]+(\d+)", notes, re.I)
    if rm_test:
        return 1, int(rm_test.group(1)), float(rm_test.group(2)), notes

    # Lone number that plausibly is a weight (cap at 1000 to avoid tracking codes)
    # Allow period/comma after number so "20. foot out chest..." is caught.
    lone = re.match(r"^(\d+(?:\.\d+)?)\s*(?:lb|lbs|#)?(?:[\s,.]|$)", notes)
    if lone:
        candidate = float(lone.group(1))
        if 10 <= candidate <= 1000:
            return (s or 1), (r or 1), candidate, notes

    # Everything else: treat as textual note confirming plan execution
    return (s or 1), (r or 1), (w or 0.0), notes


def _parse_multi_group(cell: str, planned_sets, planned_reps):
    """
    Detect patterns like '155 2x5, 135 2x8' or '18" 165 2x5, 135 2x8'.
    Returns list of (sets, reps, weight, notes) or [] if not multi-group.

    When the second number in NxM is > 50, interpret it as a weight rather
    than a rep count (e.g. '3x275' = 3 reps at 275 lbs, not 3 sets x 275 reps).
    """
    cell = _preprocess_db_notation(cell)  # "50s" → "50"
    pattern = re.compile(
        r"(?:(\d+(?:\.\d+)?)\s*(?:lb|lbs|#|kg)?(?:\s+\w+)?\s*)?"
        r"(\d+)[xX×](\d+)"
    )
    matches = list(pattern.finditer(cell))
    if len(matches) < 1:
        return []
    last_end = matches[-1].end()
    trailing = cell[last_end:].strip().strip(",").strip()
    groups = []
    for mi, m in enumerate(matches):
        prefix_w = float(m.group(1)) if m.group(1) else 0.0
        a, b = int(m.group(2)), int(m.group(3))
        # If no prefix weight, check immediately after this match for "NxM W" format
        if prefix_w == 0 and b <= 50:
            seg_end = matches[mi + 1].start() if mi + 1 < len(matches) else len(cell)
            after_seg = cell[m.end():seg_end]
            wm_post = re.search(r"^\s*(\d+(?:\.\d+)?)\s*(?:lb|lbs|#|kg)?(?:\s|,|$)", after_seg)
            if wm_post:
                candidate = float(wm_post.group(1))
                if candidate > max(a, b):  # must be plausibly a weight, not a rep count
                    prefix_w = candidate
        if b > 50:
            # "3x275" → 3 reps at 275 lbs (ramp/RM format)
            groups.append((1, a, float(b), trailing))
        else:
            groups.append((a, b, prefix_w, trailing))
    return groups


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_month_day(s: str, year_hint: int, prev_month: int = None):
    s = s.strip()
    m = re.match(r"^(\d{1,2})[/\-](\d{1,2})$", s)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = year_hint
    if prev_month and month < prev_month and prev_month >= 10:
        year += 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def sheet_year(sheet_name: str):
    m = re.match(r"(\d{4})-(\d{2})", sheet_name)
    return (int(m.group(1)), int(m.group(2))) if m else (2025, 1)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

class Entry:
    __slots__ = ("dt","lift_id","lift_name","sets","reps","weight","notes",
                 "source","raw","flag")
    def __init__(self, dt, lift_id, lift_name, sets, reps, weight,
                 notes, source, raw, flag=""):
        self.dt = dt
        self.lift_id = lift_id
        self.lift_name = lift_name
        self.sets = sets
        self.reps = reps
        self.weight = weight
        self.notes = notes
        self.source = source
        self.raw = raw
        self.flag = flag


# ---------------------------------------------------------------------------
# Helper: fill missing session dates
# ---------------------------------------------------------------------------

def _fill_missing_dates(session_dates, all_sessions, default_interval):
    if not all_sessions:
        return
    known = [(k, v) for k, v in session_dates.items() if k in all_sessions]
    if not known:
        return
    known.sort()
    earliest_k, _ = known[0]
    idx = all_sessions.index(earliest_k)
    for i in range(idx - 1, -1, -1):
        k = all_sessions[i]
        if k not in session_dates:
            session_dates[k] = session_dates[all_sessions[i + 1]] - default_interval
    for i in range(len(all_sessions)):
        k = all_sessions[i]
        if k not in session_dates and i > 0:
            session_dates[k] = session_dates[all_sessions[i - 1]] + default_interval


# ---------------------------------------------------------------------------
# Parser: 2025-03
# ---------------------------------------------------------------------------

def parse_2025_03(rows, sheet_name):
    entries = []
    year, _ = sheet_year(sheet_name)
    session_dates = {}
    row_dates = {}   # row_idx → date for rows with an explicit date annotation
    last_month = 3

    for ri, row in enumerate(rows[1:], start=1):
        if len(row) < 2 or not row[0].strip().isdigit() or not row[1].strip().isdigit():
            continue
        week, day = int(row[0]), int(row[1])
        for ci in [9, 10]:
            if len(row) > ci and row[ci].strip():
                d = parse_month_day(row[ci].strip(), year, last_month)
                if d:
                    row_dates[ri] = d                          # per-row date
                    session_dates.setdefault((week, day), d)   # anchor for block
                    last_month = d.month
                    break  # use first date col that has a value

    all_sessions = sorted({
        (int(r[0]), int(r[1]))
        for r in rows[1:]
        if len(r) >= 2 and r[0].strip().isdigit() and r[1].strip().isdigit()
    })

    # Compute median inter-session interval from actual dated sessions
    if len(session_dates) >= 2:
        sorted_known = sorted(session_dates.items())
        pos_intervals = sorted(
            (sorted_known[i+1][1] - sorted_known[i][1]).days
            for i in range(len(sorted_known) - 1)
            if (sorted_known[i+1][1] - sorted_known[i][1]).days > 0
        )
        median_interval = timedelta(days=pos_intervals[len(pos_intervals) // 2]) if pos_intervals else timedelta(days=4)
    else:
        median_interval = timedelta(days=4)
    _fill_missing_dates(session_dates, all_sessions, median_interval)

    for ri, row in enumerate(rows[1:], start=1):
        if len(row) < 4 or not row[0].strip().isdigit() or not row[1].strip().isdigit():
            continue
        week, day = int(row[0]), int(row[1])
        lift_name = row[3].strip()
        if not lift_name:
            continue
        lift_id, lift_display = resolve_lift(lift_name)
        if not lift_id:
            continue

        scheme = row[5].strip() if len(row) > 5 else ""
        planned_weight_s = row[7].strip() if len(row) > 7 else ""
        notes_s = row[8].strip() if len(row) > 8 else ""
        if not notes_s:
            continue

        ps, pr = parse_sets_reps_scheme(scheme)
        pw = parse_weight(planned_weight_s)
        sets, reps, weight, notes_clean = extract_performance(notes_s, ps, pr, pw)
        if sets is None:
            continue

        # Use per-row date annotation when available; fall back to block anchor
        dt = row_dates.get(ri) or session_dates.get((week, day))
        if not dt:
            continue

        entries.append(Entry(dt, lift_id, lift_display, sets, reps,
                             weight or 0.0, notes_clean, sheet_name,
                             f"W{week}D{day}|{scheme}|{planned_weight_s}|{notes_s}"))
    return entries


# ---------------------------------------------------------------------------
# Parser: 2025-07
# ---------------------------------------------------------------------------

def parse_2025_07(rows, sheet_name):
    entries = []
    year, _ = sheet_year(sheet_name)
    session_dates = {}
    last_month = 7

    for row in rows[1:]:
        if len(row) < 2 or not row[0].strip().isdigit() or not row[1].strip().isdigit():
            continue
        week, day = int(row[0]), int(row[1])
        for ci in [7, 6]:
            if len(row) > ci:
                d = parse_month_day(row[ci].strip(), year, last_month)
                if d:
                    session_dates.setdefault((week, day), d)
                    last_month = d.month
                    break

    all_sessions = sorted({
        (int(r[0]), int(r[1]))
        for r in rows[1:]
        if len(r) >= 2 and r[0].strip().isdigit() and r[1].strip().isdigit()
    })
    _fill_missing_dates(session_dates, all_sessions, timedelta(days=3))

    for row in rows[1:]:
        if len(row) < 3 or not row[0].strip().isdigit() or not row[1].strip().isdigit():
            continue
        week, day = int(row[0]), int(row[1])
        lift_name = row[2].strip()
        if not lift_name:
            continue
        lift_id, lift_display = resolve_lift(lift_name)
        if not lift_id:
            continue

        scheme   = row[3].strip() if len(row) > 3 else ""
        load_s   = row[5].strip() if len(row) > 5 else ""
        notes_s  = row[6].strip() if len(row) > 6 else ""
        if not notes_s:
            continue

        ps, pr = parse_sets_reps_scheme(scheme)
        pw = parse_weight(load_s)
        sets, reps, weight, notes_clean = extract_performance(notes_s, ps, pr, pw)
        if sets is None:
            continue

        dt = session_dates.get((week, day))
        if not dt:
            continue

        entries.append(Entry(dt, lift_id, lift_display, sets, reps,
                             weight or 0.0, notes_clean, sheet_name,
                             f"W{week}D{day}|{scheme}|{load_s}|{notes_s}"))
    return entries


# ---------------------------------------------------------------------------
# Parser: 2025-08
# ---------------------------------------------------------------------------

def parse_2025_08(rows, sheet_name):
    entries = []
    year, _ = sheet_year(sheet_name)
    session_dates = {}
    row_dates = {}   # row_idx → date for rows with an explicit date annotation
    last_month = 7

    def week_day(row):
        ws = row[0].strip() if row else ""
        ds = row[1].strip() if len(row) > 1 else ""
        if not ws.isdigit():
            return None, None
        w = int(ws)
        if re.match(r"^\d{1,2}/\d{1,2}$", ds):
            d = parse_month_day(ds, year, last_month)
            return w, d
        return w, (int(ds) if ds.isdigit() else None)

    # Pass 1: collect explicit date annotations
    for ri, row in enumerate(rows[1:], start=1):
        w, d_or_day = week_day(row)
        if w is None:
            continue
        if isinstance(d_or_day, date):
            session_dates.setdefault((w, 0), d_or_day)
            row_dates[ri] = d_or_day
            continue
        day = d_or_day or 0
        for ci in [7, 6]:
            if len(row) > ci:
                dv = parse_month_day(row[ci].strip(), year, last_month)
                if dv:
                    row_dates[ri] = dv
                    session_dates.setdefault((w, day), dv)
                    last_month = dv.month
                    break

    # Collect (week, day) pairs that have at least one recognized lift.
    # Excluding accessory-only days (Day 4, Day 5) prevents them from padding
    # the date-fill intervals and pushing real sessions to wrong dates.
    all_int_days = sorted({
        (int(r[0]), int(r[1]))
        for r in rows[1:]
        if (len(r) >= 2 and r[0].strip().isdigit() and r[1].strip().isdigit()
            and not re.match(r"^\d{1,2}/\d{1,2}$", r[1].strip())
            and len(r) > 2 and resolve_lift(r[2].strip())[0] is not None)
    })

    # Intra-week interpolation: fill sessions sandwiched between dated sessions in same week
    for (w, d) in all_int_days:
        if (w, d) in session_dates:
            continue
        same_wk = {dd: session_dates[(ww, dd)] for (ww, dd) in session_dates if ww == w}
        lows  = [dd for dd in same_wk if dd < d]
        highs = [dd for dd in same_wk if dd > d]
        if lows and highs:
            bd, ad = max(lows), min(highs)
            t = (d - bd) / (ad - bd)
            span = (same_wk[ad] - same_wk[bd]).days
            session_dates[(w, d)] = same_wk[bd] + timedelta(days=int(t * span + 0.5))

    all_sessions = sorted(set(session_dates.keys()) | set(all_int_days))
    _fill_missing_dates(session_dates, all_sessions, timedelta(days=2))

    # Strava dates for orphaned rows (no week/day columns) — computed after fill so
    # max(session_dates) reflects extrapolated end-of-sheet dates, not just annotated ones.
    # Each orphaned row gets the next consecutive Strava date (sequential assignment).
    _orphan_iter = iter([])
    if session_dates and _strava_dates:
        last_known = max(session_dates.values())
        _orphan_iter = iter(sorted(d for d in _strava_dates if d > last_known))

    # Pass 2: generate entries
    for ri, row in enumerate(rows[1:], start=1):
        w, d_or_day = week_day(row)
        if w is None:
            # Orphaned row: no week number but may have a recognized lift.
            # Consume the next sequential Strava date only when we're about to emit an entry.
            if len(row) > 2:
                lift_name = row[2].strip()
                if lift_name:
                    lift_id, lift_display = resolve_lift(lift_name)
                    if lift_id:
                        notes = row[6].strip() if len(row) > 6 else ""
                        if not notes:
                            continue
                        sets, reps, weight, notes_clean = extract_performance(
                            notes, None, None, None)
                        if sets is None:
                            continue
                        orphan_dt = next(_orphan_iter, None)
                        if orphan_dt is None:
                            continue
                        entries.append(Entry(orphan_dt, lift_id, lift_display,
                                             sets, reps, weight or 0.0,
                                             notes_clean, sheet_name,
                                             f"orphan|{orphan_dt}|{notes}"))
            continue
        day = 0 if isinstance(d_or_day, date) else (d_or_day or 0)
        lift_name = row[2].strip() if len(row) > 2 else ""
        if not lift_name:
            continue
        lift_id, lift_display = resolve_lift(lift_name)
        if not lift_id:
            continue

        ps_s  = row[3].strip() if len(row) > 3 else ""
        pr_s  = row[4].strip() if len(row) > 4 else ""
        w_s   = row[5].strip() if len(row) > 5 else ""
        notes = row[6].strip() if len(row) > 6 else ""
        if not notes:
            continue

        try:
            ps = int(ps_s) if ps_s.isdigit() else None
            pr = int(pr_s) if pr_s.isdigit() else None
        except ValueError:
            ps = pr = None

        pw = parse_weight(w_s)
        sets, reps, weight, notes_clean = extract_performance(notes, ps, pr, pw)
        if sets is None:
            continue

        # Use per-row date annotation when available; fall back to block anchor
        dt = row_dates.get(ri) or session_dates.get((w, day))
        if not dt:
            continue

        entries.append(Entry(dt, lift_id, lift_display, sets, reps,
                             weight or 0.0, notes_clean, sheet_name,
                             f"W{w}D{day}|{ps_s}x{pr_s}|{w_s}|{notes}"))
    return entries


# ---------------------------------------------------------------------------
# Parser: 2025-09  (pivot, sessions as columns with "start M/D" headers)
# ---------------------------------------------------------------------------

def parse_2025_09(rows, sheet_name):
    entries = []
    if not rows:
        return entries

    header = rows[0]
    year = 2025
    last_month = 8

    cycle_cols = []
    for i, cell in enumerate(header):
        if i < 4:
            continue
        m = re.search(r"(\d{1,2}/\d{1,2})", str(cell))
        if m:
            d = parse_month_day(m.group(1), year, last_month)
            if d:
                cycle_cols.append((i, d))
                last_month = d.month

    if not cycle_cols:
        return entries

    day_order = {}
    for row in rows[1:]:
        label = row[0].strip() if row else ""
        if label and label not in day_order:
            day_order[label] = len(day_order)

    def session_date(cycle_start, cycle_end, day_label):
        offset = day_order.get(day_label, 0)
        n = len(day_order) or 4
        window = _strava_window(cycle_start, cycle_end)
        if len(window) >= n:
            return window[offset]
        span = (cycle_end - cycle_start).days
        return cycle_start + timedelta(days=int(offset * span / n + 0.5))

    for row in rows[1:]:
        if len(row) < 2:
            continue
        day_label = row[0].strip()
        lift_name = row[1].strip()
        if not lift_name:
            continue
        lift_id, lift_display = resolve_lift(lift_name)
        if not lift_id:
            continue

        scheme = row[2].strip() if len(row) > 2 else ""
        ps, pr = parse_sets_reps_scheme(scheme)

        for ci, (col_i, cycle_start) in enumerate(cycle_cols):
            if col_i >= len(row):
                continue
            cell = row[col_i].strip()
            if not cell:
                continue

            cycle_end = cycle_cols[ci + 1][1] if ci + 1 < len(cycle_cols) else cycle_start + timedelta(days=14)
            dt = session_date(cycle_start, cycle_end, day_label)

            groups = _parse_multi_group(cell, ps, pr)
            if groups:
                for g_sets, g_reps, g_weight, g_notes in groups:
                    entries.append(Entry(dt, lift_id, lift_display,
                                        g_sets, g_reps, g_weight or 0.0,
                                        g_notes, sheet_name,
                                        f"{day_label}|col{col_i}|{cell}"))
            else:
                sets, reps, weight, notes_clean = extract_performance(cell, ps, pr, None)
                if sets is None:
                    continue
                entries.append(Entry(dt, lift_id, lift_display,
                                     sets, reps, weight or 0.0,
                                     notes_clean, sheet_name,
                                     f"{day_label}|col{col_i}|{cell}"))
    return entries


# ---------------------------------------------------------------------------
# Parser: 2025-11  (pivot, each column = one ROTATION START DATE;
#                   4 sections = 4 sessions within that rotation)
# ---------------------------------------------------------------------------

def parse_2025_11(rows, sheet_name):
    """
    Structure:
      - Header row: first 5 cols are lift metadata; remaining cols are rotation start dates.
      - Blank-header columns may exist (date estimated by interpolation).
      - Data rows are grouped into 4 sections separated by blank rows in col 0.
        Each section = one workout session within the rotation.
      - Ditto cells (") mean "same as the previous rotation for this lift".
      - Ditto+text cells (" text) mean "same weight/sets/reps, add this note".
    """
    entries = []
    if not rows:
        return entries

    header = rows[0]
    year = 2025
    last_month = 11

    # --- Step 1: Find all session columns (with date or blank-but-has-data) ---
    # We'll store (col_index, date_or_None) and fill in None by interpolation later.
    raw_cols = []  # list of (col_index, date|None)
    for i, cell in enumerate(header):
        if i < 5:
            continue
        cell_s = str(cell).strip()
        d = parse_month_day(cell_s, year, last_month) if cell_s else None
        if d:
            raw_cols.append((i, d))
            last_month = d.month
            year = d.year   # carry year forward so Jan/Feb correctly become 2026
        elif not cell_s:
            # Blank header — check for any data in this column
            has_data = any(len(r) > i and str(r[i]).strip() for r in rows[1:])
            if has_data:
                raw_cols.append((i, None))

    # Interpolate dates for blank-header columns.
    # Prefer the first Strava date in the gap over a simple midpoint.
    for j in range(len(raw_cols)):
        col_i, dt = raw_cols[j]
        if dt is None:
            prev_dt = next((raw_cols[k][1] for k in range(j - 1, -1, -1) if raw_cols[k][1]), None)
            next_dt = next((raw_cols[k][1] for k in range(j + 1, len(raw_cols)) if raw_cols[k][1]), None)
            if prev_dt and next_dt:
                gap = sorted(d for d in _strava_dates if prev_dt < d < next_dt)
                if gap:
                    raw_cols[j] = (col_i, gap[0])
                else:
                    span = (next_dt - prev_dt).days
                    raw_cols[j] = (col_i, prev_dt + timedelta(days=span // 2))
            elif prev_dt:
                after = sorted(d for d in _strava_dates if d > prev_dt)
                raw_cols[j] = (col_i, after[0] if after else prev_dt + timedelta(days=7))
            elif next_dt:
                before = sorted(d for d in _strava_dates if d < next_dt)
                raw_cols[j] = (col_i, before[-1] if before else next_dt - timedelta(days=7))

    rotation_cols = [(ci, dt) for ci, dt in raw_cols if dt is not None]
    if not rotation_cols:
        return entries

    # --- Step 2: Identify sections (consecutive data rows between blank rows) ---
    sections = []  # list of lists of row indices
    current = []
    for i, row in enumerate(rows[1:], start=1):
        name = row[0].strip() if row else ""
        if name:
            current.append(i)
        else:
            if current:
                sections.append(current)
                current = []
    if current:
        sections.append(current)

    n_sections = len(sections)  # expect 4

    # --- Step 3: Compute per-section session dates for each rotation ---
    def section_date(rot_idx, sect_idx):
        _, rot_start = rotation_cols[rot_idx]
        if rot_idx + 1 < len(rotation_cols):
            rot_end = rotation_cols[rot_idx + 1][1]
        else:
            rot_end = rot_start + timedelta(days=7)
        window = _strava_window(rot_start, rot_end)
        if len(window) >= n_sections:
            return window[sect_idx]
        span = (rot_end - rot_start).days
        return rot_start + timedelta(days=int(sect_idx * span / n_sections + 0.5))

    # --- Step 4: Parse cells with ditto carry-forward ---
    # last_known_cell[(row_idx, rot_list_idx)] = resolved cell string
    last_known_cell = {}

    for sect_idx, row_indices in enumerate(sections):
        for row_idx in row_indices:
            row = rows[row_idx]
            lift_name = row[0].strip() if row else ""
            lift_id, lift_display = resolve_lift(lift_name)
            if not lift_id:
                continue

            scheme = row[2].strip() if len(row) > 2 else ""
            ps, pr = parse_sets_reps_scheme(scheme)

            for rot_idx, (col_i, _) in enumerate(rotation_cols):
                cell = row[col_i].strip() if col_i < len(row) else ""

                # Resolve ditto marks
                if is_ditto(cell):
                    # Find most recent prior rotation with a known value
                    cell = next(
                        (last_known_cell[(row_idx, k)]
                         for k in range(rot_idx - 1, -1, -1)
                         if (row_idx, k) in last_known_cell),
                        ""
                    )
                    if not cell:
                        continue
                else:
                    suffix = ditto_suffix(cell)
                    if suffix is not None:
                        # e.g. '" go up' — use prev weight/sets/reps but keep suffix as note
                        prev = next(
                            (last_known_cell[(row_idx, k)]
                             for k in range(rot_idx - 1, -1, -1)
                             if (row_idx, k) in last_known_cell),
                            ""
                        )
                        # Parse weight from prev to carry it, append suffix as the note text
                        cell = (prev + " " + suffix).strip() if prev else suffix

                if not cell:
                    continue

                last_known_cell[(row_idx, rot_idx)] = cell
                dt = section_date(rot_idx, sect_idx)

                groups = _parse_multi_group(cell, ps, pr)
                if groups:
                    for g_sets, g_reps, g_weight, g_notes in groups:
                        entries.append(Entry(dt, lift_id, lift_display,
                                            g_sets, g_reps, g_weight or 0.0,
                                            g_notes, sheet_name,
                                            f"s{sect_idx}|rot{rot_idx}|{dt}|{cell}"))
                else:
                    sets, reps, weight, notes_clean = extract_performance(cell, ps, pr, None)
                    if sets is None:
                        continue
                    entries.append(Entry(dt, lift_id, lift_display,
                                        sets, reps, weight or 0.0,
                                        notes_clean, sheet_name,
                                        f"s{sect_idx}|rot{rot_idx}|{dt}|{cell}"))
    return entries


# ---------------------------------------------------------------------------
# Parser: 2025-09-08  (pivot — sessions as columns, covers Sep–Nov 2025)
#   Header: lift | detail | day | category | last | date1 | date2 | ...
#   Skip col 4 ("last" = historical reference). Sessions start at col 5.
# ---------------------------------------------------------------------------

def parse_2025_09_08(rows, sheet_name):
    entries = []
    if not rows:
        return entries

    header = rows[0]
    year = 2025
    last_month = 9

    # Parse session dates from header cols 5+
    session_cols = []  # [(col_index, date), ...]
    for i, cell in enumerate(header):
        if i < 5:
            continue
        m = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-]\d{2,4})?", str(cell))
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            try:
                d = date(year, month, day)
                if d.month < last_month - 2:
                    year += 1
                    d = date(year, month, day)
                session_cols.append((i, d))
                last_month = d.month
            except ValueError:
                pass

    if not session_cols:
        return entries

    # Build day_label order from col 2 (for within-cycle date offset)
    day_order = {}
    for row in rows[1:]:
        if len(row) > 2:
            label = row[2].strip()
            if label and label not in day_order:
                day_order[label] = len(day_order)

    def section_date(cycle_start, cycle_end, day_label):
        offset = day_order.get(day_label, 0)
        n = len(day_order) or 4
        window = _strava_window(cycle_start, cycle_end)
        if len(window) >= n:
            return window[offset]
        span = (cycle_end - cycle_start).days
        return cycle_start + timedelta(days=int(offset * span / n + 0.5))

    for row in rows[1:]:
        if not row:
            continue
        lift_name = row[0].strip() if row else ""
        if not lift_name:
            continue
        lift_id, lift_display = resolve_lift(lift_name)
        if not lift_id:
            continue

        detail = row[1].strip() if len(row) > 1 else ""
        ps, pr = parse_sets_reps_scheme(detail)
        day_label = row[2].strip() if len(row) > 2 else ""

        for ci, (col_i, cycle_start) in enumerate(session_cols):
            if col_i >= len(row):
                continue
            cell = row[col_i].strip()
            if not cell:
                continue

            cycle_end = session_cols[ci + 1][1] if ci + 1 < len(session_cols) else cycle_start + timedelta(days=14)
            dt = section_date(cycle_start, cycle_end, day_label) if day_label else cycle_start

            groups = _parse_multi_group(cell, ps, pr)
            if groups:
                for g_sets, g_reps, g_weight, g_notes in groups:
                    entries.append(Entry(dt, lift_id, lift_display,
                                        g_sets, g_reps, g_weight or 0.0,
                                        g_notes, sheet_name,
                                        f"col{col_i}|{dt}|{cell}"))
            else:
                sets, reps, weight, notes_clean = extract_performance(cell, ps, pr, None)
                if sets is None:
                    continue
                entries.append(Entry(dt, lift_id, lift_display,
                                     sets, reps, weight or 0.0,
                                     notes_clean, sheet_name,
                                     f"col{col_i}|{dt}|{cell}"))

    return entries


# ---------------------------------------------------------------------------
# Parser: 2026-02  (running log — date header rows + lift/notes pairs)
# ---------------------------------------------------------------------------

def parse_2026_02(rows, sheet_name):
    entries = []
    year = 2026
    current_date = None
    last_month = 2

    for row in rows:
        if not row:
            continue
        first = row[0].strip() if row[0] else ""
        d = parse_month_day(first, year, last_month)
        if d:
            current_date = d
            last_month = d.month
            continue
        if current_date is None or not first:
            continue

        lift_id, lift_display = resolve_lift(first)
        if not lift_id:
            continue

        notes_s = row[1].strip() if len(row) > 1 else ""
        if not notes_s:
            continue

        sets, reps, weight, notes_clean = extract_performance(notes_s, None, None, None)
        if sets is None:
            sets, reps, weight = 1, 1, 0.0

        entries.append(Entry(current_date, lift_id, lift_display,
                             sets, reps, weight or 0.0,
                             notes_clean, sheet_name,
                             f"{current_date}|{notes_s}"))
    return entries


# ---------------------------------------------------------------------------
# Reasonableness checker
# ---------------------------------------------------------------------------

def check_reasonableness(entries):
    """
    Flag suspicious entries. Returns entries with .flag set where applicable.
    Also prints a summary report.
    """
    from collections import defaultdict

    # Group by lift_id, sorted by date
    by_lift = defaultdict(list)
    for e in entries:
        by_lift[e.lift_id].append(e)
    for lift_id in by_lift:
        by_lift[lift_id].sort(key=lambda e: e.dt)

    flags = []

    for lift_id, lift_entries in by_lift.items():
        prev_weight = None

        for e in lift_entries:
            reasons = []

            # Implausible volume per entry
            if e.sets and e.reps and e.sets * e.reps > 60:
                reasons.append(f"high_volume:{e.sets}x{e.reps}={e.sets*e.reps}")

            # Weight sanity for barbell lifts
            if lift_id in ("barbell_bench_press", "back_squat", "deadlift",
                           "trap_bar_deadlift", "strict_press", "rdl", "front_squat"):
                if e.weight and e.weight > 500:
                    reasons.append(f"weight_too_high:{e.weight}")
                if e.weight == 0.0:
                    reasons.append("zero_weight_barbell")

            # Large weight jump vs previous session
            if prev_weight and prev_weight > 0 and e.weight and e.weight > 0:
                ratio = e.weight / prev_weight
                if ratio > 2.0:
                    reasons.append(f"weight_jump_up:{prev_weight:.0f}→{e.weight:.0f}")
                elif ratio < 0.4:
                    reasons.append(f"weight_drop:{prev_weight:.0f}→{e.weight:.0f}")

            if reasons:
                e.flag = "; ".join(reasons)
                flags.append(e)

            if e.weight:
                prev_weight = e.weight

    print(f"\n{'='*60}")
    print(f"REASONABLENESS CHECK: {len(flags)} flagged entries")
    print(f"{'='*60}")

    by_flag_type = defaultdict(list)
    for e in flags:
        for reason in e.flag.split("; "):
            key = reason.split(":")[0]
            by_flag_type[key].append(e)

    for flag_type, flag_entries in sorted(by_flag_type.items()):
        print(f"\n  {flag_type} ({len(flag_entries)} entries):")
        for e in flag_entries[:8]:  # show up to 8 examples
            print(f"    {e.dt} {e.lift_name}: {e.sets}x{e.reps}@{e.weight}  [{e.flag}]  raw: {e.raw[:60]}")

    # Weight progression summary
    print(f"\n{'='*60}")
    print("WEIGHT PROGRESSION SUMMARY (lifts with >= 3 non-zero sessions)")
    print(f"{'='*60}")
    for lift_id, lift_entries in sorted(by_lift.items()):
        weighted = [e for e in lift_entries if e.weight and e.weight > 0]
        if len(weighted) < 3:
            continue
        first_w = weighted[0].weight
        last_w = weighted[-1].weight
        max_w = max(e.weight for e in weighted)
        dates = f"{weighted[0].dt} → {weighted[-1].dt}"
        trend = "↑" if last_w > first_w * 1.05 else ("↓" if last_w < first_w * 0.95 else "~")
        name = weighted[0].lift_name
        print(f"  {trend} {name:35s} {first_w:>6.1f} → {last_w:>6.1f}  (peak {max_w:>6.1f})  {dates}")

    return entries


# ---------------------------------------------------------------------------
# Recommend an action for each flagged entry
# ---------------------------------------------------------------------------

def suggest_action(e) -> str:
    """Return a recommendation string for a flagged entry, or '' if unflagged."""
    if not e.flag:
        return ""

    flag_types = {f.split(":")[0].strip() for f in e.flag.split(";")}
    w, d = e.weight, e.dt

    # ── specific cases ───────────────────────────────────────────────────────
    # Calf Raise 2025-12-04: "leg curls 25kg" logged under calf_raise
    if e.lift_id == "calf_raise" and d == date(2025, 12, 4):
        return "DELETE — 'leg curls 25kg' mislabeled as calf raise (wrong exercise)"

    # Back Squat / RDL 2025-11-19: dumbbell injury subs
    if d == date(2025, 11, 19) and e.lift_id in ("back_squat", "rdl") \
            and "weight_drop" in flag_types:
        return ("CONSIDER DELETE — dumbbell injury sub (50# DBs), "
                "not an actual barbell lift; skews progression chart")

    # Strict Press 2025-09-29: seated DB press sub during shoulder injury
    if e.lift_id == "strict_press" and d == date(2025, 9, 29) \
            and "weight_drop" in flag_types:
        return ("CONSIDER DELETE — seated 25# DB press sub during shoulder injury; "
                "not comparable to barbell strict press")

    # Dips 2026-02-03: bw+25 — the drop from the old 95# peak is expected
    if e.lift_id == "dips" and d == date(2026, 2, 3) \
            and "weight_drop" in flag_types:
        return ("KEEP — 25 = added weight (bw+25 3x8); "
                "large drop vs Jul peak is expected phase change")

    # ── weight_jump_up: return from injury-period dumbbell subs ─────────────
    if "weight_jump_up" in flag_types:
        if e.lift_id in ("back_squat", "rdl") and d >= date(2025, 11, 20):
            return ("KEEP — barbell return after injury-period dumbbell sub; "
                    "jump is expected (consider deleting the DB sub entry instead)")
        if e.lift_id == "calf_raise" and d == date(2025, 12, 18):
            return ("KEEP — jump resolves if the mislabeled 2025-12-04 entry is deleted")
        if e.lift_id == "bulgarian_split_squat":
            return "KEEP — return to normal load after rehab weight; legitimate"
        if e.lift_id == "barbell_bench_press":
            return "KEEP — return to barbell after shoulder injury; expected jump"
        if e.lift_id == "weighted_pull_ups":
            return "KEEP — legitimate progression (10→25 lbs added weight)"
        return "KEEP — likely legitimate; review raw note if unsure"

    # ── high_volume ──────────────────────────────────────────────────────────
    if "high_volume" in flag_types:
        return ("KEEP — reps field = yards (farmer's carry); "
                "volume calc is inflated but the data entry is correct")

    # ── zero_weight_barbell ──────────────────────────────────────────────────
    if "zero_weight_barbell" in flag_types:
        return "REVIEW — barbell lift logged with 0 weight; check raw note"

    return "REVIEW — check raw note"


# ---------------------------------------------------------------------------
# Write preview to Google Sheets
# ---------------------------------------------------------------------------

# Row background colours keyed on the leading recommendation word
_ROW_COLORS = {
    "DELETE":           {"red": 1.0,  "green": 0.80, "blue": 0.80},  # red-ish
    "CONSIDER DELETE":  {"red": 1.0,  "green": 0.92, "blue": 0.75},  # orange-ish
    "KEEP":             {"red": 0.87, "green": 0.96, "blue": 0.87},  # green-ish
    "REVIEW":           {"red": 1.0,  "green": 0.95, "blue": 0.60},  # yellow (old default)
}


def write_preview(service, entries):
    ss = service.spreadsheets()

    # Delete existing preview sheet if present
    meta = ss.get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = [s["properties"] for s in meta["sheets"]
                if s["properties"]["title"] == PREVIEW_SHEET_NAME]

    requests = []
    if existing:
        requests.append({"deleteSheet": {"sheetId": existing[0]["sheetId"]}})
    requests.append({"addSheet": {"properties": {"title": PREVIEW_SHEET_NAME}}})
    ss.batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests}).execute()

    meta2 = ss.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_id = next(
        s["properties"]["sheetId"] for s in meta2["sheets"]
        if s["properties"]["title"] == PREVIEW_SHEET_NAME
    )

    sorted_entries = sorted(entries, key=lambda x: (x.dt, x.lift_id))

    header = ["date", "lift_id", "lift_name", "sets", "reps", "weight", "notes",
              "flag", "recommendation", "your_decision", "source_sheet", "raw_text"]
    data_rows = [header]
    for e in sorted_entries:
        rec = suggest_action(e)
        data_rows.append([
            e.dt.strftime("%Y-%m-%d"),
            e.lift_id,
            e.lift_name,
            e.sets or "",
            e.reps or "",
            e.weight if e.weight is not None else 0,
            e.notes,
            e.flag,
            rec,
            "",          # your_decision — user fills this in
            e.source,
            e.raw,
        ])

    ss.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{PREVIEW_SHEET_NAME}'!A1",
        valueInputOption="RAW",
        body={"values": data_rows}
    ).execute()

    # ── formatting ────────────────────────────────────────────────────────────
    fmt_requests = [
        # Freeze header row
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id,
                           "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"
        }},
        # Auto-resize all columns
        {"autoResizeDimensions": {
            "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": len(header)}
        }},
        # Bold the header row
        {"repeatCell": {
            "range": {"sheetId": sheet_id,
                      "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            }},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"
        }},
    ]

    # Colour-code flagged rows by recommendation type
    flagged_row_indices = []
    for i, e in enumerate(sorted_entries):
        if not e.flag:
            continue
        ri = i + 1  # 0-indexed row (header = 0)
        flagged_row_indices.append(ri)
        rec = suggest_action(e)
        lead = rec.split("—")[0].strip() if rec else "REVIEW"
        bg = _ROW_COLORS.get(lead, _ROW_COLORS["REVIEW"])
        fmt_requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id,
                      "startRowIndex": ri, "endRowIndex": ri + 1},
            "cell": {"userEnteredFormat": {"backgroundColor": bg}},
            "fields": "userEnteredFormat.backgroundColor"
        }})

    # Drop-down validation on "your_decision" column (col index 9)
    decision_col = header.index("your_decision")
    fmt_requests.append({"setDataValidation": {
        "range": {
            "sheetId": sheet_id,
            "startRowIndex": 1, "endRowIndex": len(data_rows),
            "startColumnIndex": decision_col,
            "endColumnIndex": decision_col + 1,
        },
        "rule": {
            "condition": {
                "type": "ONE_OF_LIST",
                "values": [
                    {"userEnteredValue": "keep"},
                    {"userEnteredValue": "delete"},
                    {"userEnteredValue": "override_weight"},
                    {"userEnteredValue": "override_sets_reps"},
                ],
            },
            "showCustomUi": True,
            "strict": False,
        },
    }})

    ss.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                   body={"requests": fmt_requests}).execute()

    print(f"Preview written: {len(data_rows) - 1} entries → '{PREVIEW_SHEET_NAME}'")
    print(f"  ({len(flagged_row_indices)} flagged rows colour-coded by recommendation)")


# ---------------------------------------------------------------------------
# Manual corrections and filters
# ---------------------------------------------------------------------------

def apply_manual_corrections(entries):
    """Apply hardcoded per-entry corrections and exclusions."""

    # ----------------------------------------------------------------
    # 1. Weight-only overrides: (date, lift_id) → new weight in lbs
    # ----------------------------------------------------------------
    weight_overrides = {
        (date(2025,  4,  9), "barbell_bench_press"): 125.0,
        (date(2025,  4, 15), "barbell_bench_press"): 165.0,
        (date(2025,  4,  6), "farmers_carry"):        50.0,
        (date(2025,  5, 15), "farmers_carry"):         60.0,
        (date(2025,  7,  4), "dips"):                  55.0,
        (date(2025, 12,  4), "rdl"):                   97.0,  # 22*2 kg → lbs
        (date(2025, 12,  4), "back_squat"):           188.0,  # smith 85 kg → lbs (user)
        (date(2025, 12, 11), "barbell_bench_press"):  160.0,
        (date(2025, 12, 18), "back_squat"):           205.0,  # user confirmed
    }
    for e in entries:
        new_w = weight_overrides.get((e.dt, e.lift_id))
        if new_w is not None:
            e.weight = new_w

    # ----------------------------------------------------------------
    # 1b. Trap-bar deadlift calibration: all entries before 2025-12-11
    #     were logged 20 lbs light (bar + plates miscounted); add 20.
    # ----------------------------------------------------------------
    for e in entries:
        if e.lift_id == "trap_bar_deadlift" and e.dt < date(2025, 12, 11):
            e.weight = (e.weight or 0.0) + 20.0

    # ----------------------------------------------------------------
    # 2. Sets/reps overrides: (date, lift_id) → (sets, reps)
    # ----------------------------------------------------------------
    sets_reps_overrides = {
        (date(2025, 6, 11), "back_squat"): (1, 5),
    }
    for e in entries:
        override = sets_reps_overrides.get((e.dt, e.lift_id))
        if override:
            e.sets, e.reps = override

    # ----------------------------------------------------------------
    # 3. Lift-type change: 2025-12-03 calf_raise → leg_extension @25 kg
    # ----------------------------------------------------------------
    for e in entries:
        if e.dt == date(2025, 12, 3) and e.lift_id == "calf_raise":
            e.lift_id = "leg_extension"
            e.lift_name = "Leg Extension"
            e.weight = round(25 * 2.20462)  # 25 kg → 55 lbs

    # ----------------------------------------------------------------
    # 4. Delete specific entries by (date, lift_id, sets, reps)
    # ----------------------------------------------------------------
    deletions = {
        # "160 3x5. good, go 3x6" — the "3x5" was the plan, "go 3x6" was parsed
        # as a second entry; user wants only the 3x6 entry kept
        (date(2025, 12, 11), "barbell_bench_press", 3, 5),
        # Injury-period zero-weight substitution entries
        (date(2025, 10,  8), "barbell_bench_press", 3, 20),  # Upper 1 offset=0 → Strava 10/8
        (date(2025, 10,  6), "strict_press",        3,  8),  # Upper 2 in 10/2–10/8 cycle
        (date(2025, 10, 10), "strict_press",        3, 20),  # Upper 2 in 10/8–10/16 cycle
        (date(2025, 10, 31), "strict_press",        3, 10),  # Upper 2 in 10/28–11/3 cycle
        # Spurious parse from note text
        (date(2025,  9, 20), "front_squat",         3,  7),
        # User decisions from import-preview review
        (date(2025,  9, 29), "strict_press",        3, 10),  # seated DB press sub during injury
        (date(2025, 10, 16), "barbell_bench_press", 3, 10),  # DB bench sub during injury
        (date(2025, 10, 23), "strict_press",        3,  6),  # DB press sub during injury
        (date(2025, 11, 19), "back_squat",          3, 12),  # 50# dumbbell sub (not a real squat)
        (date(2025, 11, 19), "rdl",                 3, 15),  # 50# dumbbell sub
        (date(2025, 12,  4), "calf_raise",          3,  8),  # "leg curls 25kg" mislabeled
        # Outlier cleanup (user review 2026-02)
        (date(2025, 10,  2), "barbell_bench_press", 3, 12),  # 50 lbs — injury-period low outlier
        (date(2025,  9, 22), "hammer_curl",         3, 10),  # 60 lbs — erroneous high
        (date(2025,  9, 29), "hammer_curl",         3, 12),  # 60 lbs — erroneous high
        (date(2025,  9, 14), "incline_db_curl",     3, 12),  # 50 lbs — outlier high
        (date(2025, 10, 28), "incline_db_curl",     3, 12),  # 60 lbs — outlier high
        (date(2025, 11, 11), "incline_db_curl",     3, 10),  # 60 lbs — outlier high
    }
    entries = [e for e in entries
               if (e.dt, e.lift_id, e.sets, e.reps) not in deletions]

    # ----------------------------------------------------------------
    # 5. Full replacements: remove all existing (date, lift_id) entries
    #    and insert the specified new ones
    # ----------------------------------------------------------------
    replacements = {
        # 2025-07-06 session (manually supplied — not in any sheet)
        (date(2025, 7,  6), "barbell_bench_press"):   [(4, 6, 140.0, "")],
        (date(2025, 7,  6), "rdl"):                   [(4, 8, 145.0, "")],
        (date(2025, 7,  6), "bulgarian_split_squat"): [(3, 8,  20.0, "")],
        # 2026-01-22 weighted pull-ups: ramped warm-up, 3 reps each weight
        (date(2026, 1, 22), "weighted_pull_ups"): [
            (1, 3,   0, "warmup ladder"),
            (1, 3,  10, "warmup ladder"),
            (1, 3,  15, "warmup ladder"),
            (1, 3,  20, "warmup ladder"),
            (1, 3,  25, "warmup ladder"),
        ],
        # 2025-07-17 lat pulldown: ramped sets, 10 reps each weight
        (date(2025, 7, 17), "lat_pulldown"): [
            (1, 10, 140, "ramped"),
            (1, 10, 145, "ramped"),
            (1, 10, 150, "ramped"),
        ],
        # 2025-08-03 weighted pull-ups: 25# 4/4/2
        (date(2025, 8,  3), "weighted_pull_ups"): [
            (1, 4, 25, ""),
            (1, 4, 25, ""),
            (1, 2, 25, ""),
        ],
    }
    replacement_keys = set(replacements.keys())
    new_entries = []
    for (rep_date, rep_lift), sets_data in replacements.items():
        existing = [e for e in entries if e.dt == rep_date and e.lift_id == rep_lift]
        source    = existing[0].source if existing else "manual_correction"
        raw       = existing[0].raw    if existing else "manual_correction"
        lift_name = (CURRENT_LIFT_NAMES.get(rep_lift)
                     or HISTORICAL_LIFT_NAMES.get(rep_lift)
                     or (existing[0].lift_name if existing else rep_lift))
        for s, r, w, note in sets_data:
            new_entries.append(Entry(rep_date, rep_lift, lift_name,
                                     s, r, float(w), note, source, raw))
    entries = [e for e in entries if (e.dt, e.lift_id) not in replacement_keys]
    entries.extend(new_entries)

    # ----------------------------------------------------------------
    # 6. Exclude DB rows (row entries < 100 lbs were dumbbell, not machine)
    # ----------------------------------------------------------------
    before = len(entries)
    entries = [e for e in entries if not (e.lift_id == "row" and e.weight < 100)]
    excluded = before - len(entries)
    if excluded:
        print(f"  Excluded {excluded} DB row entries (weight < 100 lbs)")

    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PARSERS = {
    "2025-03": parse_2025_03,
    "2025-07": parse_2025_07,
    "2025-08": parse_2025_08,
    "2025-09": parse_2025_09,
    "2025-09-08": parse_2025_09_08,
    "2025-11": parse_2025_11,
    "2026-02": parse_2026_02,
}


def main():
    import warnings
    warnings.filterwarnings("ignore")

    global _strava_dates
    service = get_service()
    all_entries = []
    strava_dates = load_strava_dates()
    if strava_dates:
        _strava_dates = strava_dates
        print(f"Loaded {len(strava_dates)} Strava strength dates")

    for sheet_name, parser_fn in PARSERS.items():
        json_path = os.path.join(os.path.dirname(__file__), f"sheet_{sheet_name}.json")
        if not os.path.exists(json_path):
            print(f"  Missing {json_path}, skipping")
            continue
        with open(json_path) as f:
            rows = json.load(f)
        entries = parser_fn(rows, sheet_name)
        print(f"  {sheet_name}: {len(entries)} entries parsed")
        all_entries.extend(entries)

    print(f"\nTotal entries: {len(all_entries)}")
    all_entries = apply_manual_corrections(all_entries)
    print(f"After corrections/filters: {len(all_entries)} entries")

    # Snap estimated dates to nearest Strava workout date (±4 days)
    if strava_dates:
        snapped = 0
        for e in all_entries:
            new_dt = snap_to_strava(e.dt, strava_dates)
            if new_dt != e.dt:
                e.dt = new_dt
                snapped += 1
        print(f"  Strava snapping: {snapped} entries adjusted")

    all_entries = check_reasonableness(all_entries)
    write_preview(service, all_entries)

    # Export to CSV for downstream analysis (e.g. R charts)
    csv_path = os.path.join(os.path.dirname(__file__), "entries.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date","lift_id","lift_name","sets","reps","weight","notes","flag","source"])
        for e in sorted(all_entries, key=lambda x: (x.dt, x.lift_id)):
            w.writerow([e.dt.strftime("%Y-%m-%d"), e.lift_id, e.lift_name,
                        e.sets or 0, e.reps or 0, e.weight or 0.0,
                        e.notes, e.flag, e.source])
    print(f"CSV exported → {csv_path}")


if __name__ == "__main__":
    main()
