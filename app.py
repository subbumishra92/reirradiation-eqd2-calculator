import streamlit as st
import pandas as pd
import math
import re
import streamlit.components.v1 as components

# ——— Page config ———
st.set_page_config(page_title="Re‑irradiation & Palliative OARs", layout="wide")

# ——— Common Data Definitions ———
OARS = [
    "Brain Stem", "Optic Nerve", "Optic Chiasm", "Cochlea",
    "Small Bowel", "Spinal Cord", "Cauda Equina", "Sacral Plexus"
]

OAR_CONSTRAINTS = {
    o: [{"type": "max", "value": v}]
    for o, v in {
        "Brain Stem": 54, "Optic Nerve": 54, "Optic Chiasm": 54,
        "Cochlea": 45, "Small Bowel": 52, "Spinal Cord": 45,
        "Cauda Equina": 45, "Sacral Plexus": 45
    }.items()
}

OAR_ALPHA_BETA = {
    o: (2 if o in [
        "Spinal Cord", "Optic Chiasm", "Brain Stem",
        "Optic Nerve", "Sacral Plexus", "Cauda Equina"
    ] else 3)
    for o in OARS
}

RECOVERY_FACTORS = {"<6 months": 0.00, "6–12 months": 0.25, "12+ months": 0.50}
FRACTION_OPTIONS = [1, 3, 5, 10]
EXCLUDE_3FX = {"Skin", "Cortical Bone", "Articular Cartilage"}

# ——— Radiobiology Utils ———
def bed(n: int, d: float, ab: float) -> float:
    return n * d * (1 + d / ab)

def eqd2(n: int, d: float, ab: float) -> float:
    return bed(n, d, ab) / (1 + 2 / ab)

def max_d_per_fraction(n: int, target_eqd2: float, ab: float) -> float:
    tb = target_eqd2 * (1 + 2 / ab)
    a, b, c = n / ab, n, -tb
    disc = b * b - 4 * a * c
    if disc < 0:
        return 0.0
    d1 = (-b + math.sqrt(disc)) / (2 * a)
    d2 = (-b - math.sqrt(disc)) / (2 * a)
    return max(d1, d2)

# ——— 3D‑CRT Palliative Constraints ———
THREED_CONSTRAINTS = {
    "Head and Neck": [
        {"OAR": "Brainstem",      "Preferred": "Max < 55 Gy",
                                  "Acceptable": "Max 0.03 cc 60 Gy"},
        {"OAR": "Optic Chiasm",   "Preferred": "Max < 54 Gy",
                                  "Acceptable": "Max 0.03 cc 56 Gy"},
        {"OAR": "Optic Nerve",    "Preferred": "Max < 50 Gy",
                                  "Acceptable": "Max 0.03 cc 55 Gy"},
        {"OAR": "Cochlea",        "Preferred": "V55 Gy < 5 %",
                                  "Acceptable": "Mean < 45 Gy"},
        {"OAR": "Retina",         "Preferred": "Max < 45 Gy",
                                  "Acceptable": "Max < 50 Gy"},
        {"OAR": "Lacrimal Gland", "Preferred": None,
                                  "Acceptable": "Mean < 26 Gy"},
        {"OAR": "Whole Brain",    "Preferred": None,
                                  "Acceptable": "Minimize volume ≥ 30 Gy"},
        {"OAR": "Esophagus",      "Preferred": None,
                                  "Acceptable": "Mean < 30 Gy; no hot spots"},
        {"OAR": "Parotid Glands", "Preferred": None,
                                  "Acceptable": "Mean < 26 Gy; no hot spots"},
        {"OAR": "Thyroid Gland",  "Preferred": None,
                                  "Acceptable": "Mean < 37 Gy; no hot spots"},
        {"OAR": "Oral Cavity",    "Preferred": None,
                                  "Acceptable": "Minimize volume ≥ 30 Gy"},
        {"OAR": "Spinal Cord",    "Preferred": None,
                                  "Acceptable": "As low as possible; ≤ 105 % Rx"},
        {"OAR": "Skin",           "Preferred": None,
                                  "Acceptable": "Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose", "Preferred": "< 105 %",
                                  "Acceptable": "< 108 %"},
    ],

    "Thorax": [
        {"OAR": "Lungs",          "Preferred": "V5 Gy < 42 %",
                                  "Acceptable": "V20 Gy < 37 %; Mean < 20 Gy"},
        {"OAR": "Esophagus",      "Preferred": None,
                                  "Acceptable": "Mean < 30 Gy; no hot spots"},
        {"OAR": "Brachial Plexus","Preferred": None,
                                  "Acceptable": "No hot spots"},
        {"OAR": "Heart",          "Preferred": None,
                                  "Acceptable": "V60 Gy < 33 %"},
        {"OAR": "Great Vessels",  "Preferred": None,
                                  "Acceptable": "No hot spots"},
        {"OAR": "Trachea",        "Preferred": None,
                                  "Acceptable": "Mean < 30 Gy"},
        {"OAR": "Chest Wall",     "Preferred": None,
                                  "Acceptable": "No hot spots"},
        {"OAR": "Spinal Cord",    "Preferred": None,
                                  "Acceptable": "As low as possible; ≤ 45 Gy"},
        {"OAR": "Skin",           "Preferred": None,
                                  "Acceptable": "Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose", "Preferred": "< 105 %",
                                  "Acceptable": "< 108 %"},
    ],

    "Abdomen": [
        {"OAR": "Small Bowel",   "Preferred": None,
                                 "Acceptable": "As low as possible; Max 45 Gy or 105 % Rx"},
        {"OAR": "Kidneys",       "Preferred": None,
                                 "Acceptable": "Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR": "Liver",         "Preferred": None,
                                 "Acceptable": "As low as possible; 50 % < 30 Gy"},
        {"OAR": "Stomach",       "Preferred": None,
                                 "Acceptable": "As low as possible; 25 % < 45 Gy or 105 % Rx"},
        {"OAR": "Esophagus",     "Preferred": None,
                                 "Acceptable": "Mean < 34 Gy; V60 Gy < 10 cc"},
        {"OAR": "Lungs",         "Preferred": None,
                                 "Acceptable": "V5 Gy < 42 %; V20 Gy < 37 %; Mean < 20 Gy"},
        {"OAR": "Spinal Cord",   "Preferred": None,
                                 "Acceptable": "As low as possible; ≤ 45 Gy"},
        {"OAR": "Skin",          "Preferred": None,
                                 "Acceptable": "Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose","Preferred": "< 105 %",
                                 "Acceptable": "< 108 %"},
    ],

    "Female Pelvis": [
        {"OAR": "Reproductive Organs", "Preferred": None,
                                       "Acceptable": "V20 Gy < 50 %"},
        {"OAR": "Bladder",             "Preferred": None,
                                       "Acceptable": "V50 Gy < 35 %; V45 Gy < 35 %"},
        {"OAR": "Small Bowel",         "Preferred": None,
                                       "Acceptable": "As low as possible"},
        {"OAR": "Large Bowel",         "Preferred": None,
                                       "Acceptable": "As low as possible"},
        {"OAR": "Kidneys",             "Preferred": None,
                                       "Acceptable": "Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR": "Ureter",              "Preferred": None,
                                       "Acceptable": "Dmax < 45 Gy (Stricture)"},
        {"OAR": "Skin",                "Preferred": None,
                                       "Acceptable": "Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose",      "Preferred": "< 105 %",
                                       "Acceptable": "< 108 %"},
    ],

    "Male Pelvis": [
        {"OAR": "Reproductive Organs", "Preferred": None,
                                       "Acceptable": "D0.5 cc < 42 Gy"},
        {"OAR": "Bladder",             "Preferred": None,
                                       "Acceptable": "D0.5 cc < 28.2 Gy"},
        {"OAR": "Small Bowel",         "Preferred": None,
                                       "Acceptable": "As low as possible"},
        {"OAR": "Large Bowel",         "Preferred": None,
                                       "Acceptable": "As low as possible"},
        {"OAR": "Kidneys",             "Preferred": None,
                                       "Acceptable": "Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR": "Ureter",              "Preferred": None,
                                       "Acceptable": "Dmax < 45 Gy (Stricture)"},
        {"OAR": "Skin",                "Preferred": None,
                                       "Acceptable": "Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose",      "Preferred": "< 105 %",
                                       "Acceptable": "< 108 %"},
    ],

    "Proximal Upper Extremity": [
        {"OAR": "Brachial Plexus", "Preferred": None,
                                   "Acceptable": "No hot spots"},
        {"OAR": "Skin",            "Preferred": None,
                                   "Acceptable": "No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose",  "Preferred": "< 105 %",
                                   "Acceptable": "< 108 %"},
    ],

    "Distal Upper Extremity": [
        {"OAR": "Skin",           "Preferred": None,
                                  "Acceptable": "No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose", "Preferred": "< 105 %",
                                  "Acceptable": "< 108 %"},
    ],

    "Proximal Lower Extremity": [
        {"OAR": "Skin",           "Preferred": None,
                                  "Acceptable": "No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose", "Preferred": "< 105 %",
                                  "Acceptable": "< 108 %"},
    ],

    "Distal Lower Extremity": [
        {"OAR": "Skin",           "Preferred": None,
                                  "Acceptable": "No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR": "Max Point Dose", "Preferred": "< 105 %",
                                  "Acceptable": "< 108 %"},
    ]
}

# ——— Normalize unicode subscripts, tidy spaces ———
sub_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
for rows in THREED_CONSTRAINTS.values():
    for row in rows:
        for col in ("Preferred", "Acceptable"):
            txt = row[col]
            if not txt:
                continue
            s = txt.translate(sub_map)
            s = re.sub(r"\s*\(\s*0\.03\s*cc\s*\)\s*", " 0.03 cc ", s)
            s = re.sub(r"\bV\s*([\d\.]+)\s*(?=[<≥])", r"V\1 Gy ", s)
            s = re.sub(r"\s+", " ", s).strip()
            row[col] = s

# ——— SBRT Constraints (intracranial + body) ———
SBRT_INTRACRANIAL = [
    {"OAR": "Optic Pathway", "Metric": "D0.1cc",
     "3fx_opt": None, "3fx_man": 15, "5fx_opt": None, "5fx_man": 22.5,
     "Endpoint": "Optic Neuritis"},
    {"OAR": "Cochlea", "Metric": "Dmean",
     "3fx_opt": None, "3fx_man": 17.1, "5fx_opt": None, "5fx_man": 25,
     "Endpoint": "Hearing Loss"},
    {"OAR": "Brainstem", "Metric": "D0.1cc",
     "3fx_opt": 18, "3fx_man": 23.1, "5fx_opt": 23, "5fx_man": 31,
     "Endpoint": "Cranial Neuropathy"},
    {"OAR": "Spinal Canal", "Metric": "D0.1cc",
     "3fx_opt": 18, "3fx_man": 21.9, "5fx_opt": 23, "5fx_man": 30,
     "Endpoint": "Myelitis"},
]
skin_entry = {
    "OAR": "Skin",
    "Metric": "D0.03 cc / V20 Gy",
    "3fx_opt": None, "3fx_man": None,
    "5fx_opt": None, "5fx_man": "Dmax ≤ 35 Gy; V20 Gy < 10 cc",
    "Endpoint": "Ulceration"
}
SBRT_INTRACRANIAL.append(skin_entry)

SBRT_BODY = [
    {"OAR": "Brachial Plexus", "Metric": "D0.5cc",
     "3fx_opt": 24, "3fx_man": 26, "5fx_opt": 27, "5fx_man": 29,
     "Endpoint": "Neuropathy"},
    {"OAR": "Heart", "Metric": "D0.5cc",
     "3fx_opt": 24, "3fx_man": 26, "5fx_opt": 27, "5fx_man": 29,
     "Endpoint": "Pericarditis"},
    {"OAR": "Great Vessels", "Metric": "D0.5cc",
     "3fx_opt": None, "3fx_man": 45, "5fx_opt": None, "5fx_man": 53,
     "Endpoint": "Aneurysm"},
    {"OAR": "Trachea", "Metric": "D0.5cc",
     "3fx_opt": 30, "3fx_man": 32, "5fx_opt": 32, "5fx_man": 35,
     "Endpoint": "Stenosis / Fistula"},
    {"OAR": "Chest Wall", "Metric": "D0.5cc",
     "3fx_opt": 37, "3fx_man": 30, "5fx_opt": 39, "5fx_man": 32,
     "Endpoint": "Pain / Fracture"},
    {"OAR": "Lungs", "Metric": "V20 Gy",
     "3fx_opt": None, "3fx_man": "10%", "5fx_opt": None, "5fx_man": "10%",
     "Endpoint": "Pneumonitis"},
    {"OAR": "Esophagus", "Metric": "D0.5cc",
     "3fx_opt": None, "3fx_man": 25.2, "5fx_opt": 32, "5fx_man": 34,
     "Endpoint": "Stenosis / Fistula"},
    {"OAR": "Stomach", "Metric": "D5cc",
     "3fx_opt": None, "3fx_man": 16.5, "5fx_opt": 25, "5fx_man": 12,
     "Endpoint": "Ulceration / Fistula"},
    {"OAR": "Duodenum", "Metric": "D5cc",
     "3fx_opt": None, "3fx_man": 16.5, "5fx_opt": 25, "5fx_man": None,
     "Endpoint": "Ulceration"},
    {"OAR": "Small Bowel", "Metric": "D0.5cc",
     "3fx_opt": None, "3fx_man": 25.2, "5fx_opt": 30, "5fx_man": 35,
     "Endpoint": "Enteritis / Obstruction"},
    {"OAR": "Large Bowel", "Metric": "D0.5cc",
     "3fx_opt": None, "3fx_man": 28.2, "5fx_opt": None, "5fx_man": 32,
     "Endpoint": "Colitis / Fistula"},
    {"OAR": "Rectum", "Metric": "D0.5cc",
     "3fx_opt": None, "3fx_man": 28.2, "5fx_opt": None, "5fx_man": 32,
     "Endpoint": "Proctitis / Fistula"},
    {"OAR": "Cauda Equina", "Metric": "D0.1cc",
     "3fx_opt": 16, "3fx_man": 14, "5fx_opt": 32, "5fx_man": 30,
     "Endpoint": "Neuritis"},
    {"OAR": "Lumbosacral Plexus", "Metric": "D0.03 cc",
     "3fx_opt": None, "3fx_man": None, "5fx_opt": None,
     "5fx_man": "Dmax ≤ 30 Gy", "Endpoint": "Plexopathy"},
    {"OAR": "Cortical Bone", "Metric": "V25 Gy/V30 Gy",
     "3fx_opt": None, "3fx_man": None, "5fx_opt": None,
     "5fx_man": "V25 < 50 %; V30 < 35 %", "Endpoint": "Fracture"},
    {"OAR": "Articular Cartilage", "Metric": "Dmax",
     "3fx_opt": None, "3fx_man": None, "5fx_opt": None,
     "5fx_man": "Dmax ≤ 35 Gy", "Endpoint": "Joint Integrity"},
    {"OAR": "Ureter", "Metric": "Dmax",
     "3fx_opt": None, "3fx_man": 40, "5fx_opt": None, "5fx_man": 45,
     "Endpoint": "Stricture"},
]
SBRT_BODY.append(skin_entry)

SBRT_CONSTRAINTS = {
    "Head and Neck": (
        SBRT_INTRACRANIAL +
        [r for r in SBRT_BODY if r["OAR"] in ("Esophagus", "Brachial Plexus")]
    ),
    "Thorax": (
        [r for r in SBRT_INTRACRANIAL if r["OAR"] == "Spinal Canal"] +
        [r for r in SBRT_BODY if r["OAR"] in (
            "Lungs", "Esophagus", "Brachial Plexus",
            "Heart", "Great Vessels", "Trachea", "Chest Wall")]
    ),
    "Abdomen": (
        [r for r in SBRT_INTRACRANIAL if r["OAR"] == "Spinal Canal"] +
        [r for r in SBRT_BODY if r["OAR"] in (
            "Stomach", "Duodenum", "Small Bowel", "Large Bowel",
            "Kidneys", "Ureter", "Cauda Equina", "Lumbosacral Plexus")]
    ),
    "Pelvis": [
        r for r in SBRT_BODY if r["OAR"] in (
            "Skin",
            "Ureter",
            "Lumbosacral Plexus",
            "Cauda Equina",
            "Rectum",
            "Large Bowel",
            "Small Bowel"
        )
    ],

    "Proximal Upper Extremity": (
        [r for r in SBRT_BODY if r["OAR"] == "Brachial Plexus"] +
        [skin_entry] +
        [r for r in SBRT_BODY if r["OAR"] in ("Cortical Bone", "Articular Cartilage")]
    ),
    "Distal Upper Extremity": (
        [skin_entry] +
        [r for r in SBRT_BODY if r["OAR"] in ("Cortical Bone", "Articular Cartilage")]
    ),
    "Proximal Lower Extremity": (
        [skin_entry] +
        [r for r in SBRT_BODY if r["OAR"] in (
            "Cortical Bone", "Articular Cartilage", "Lumbosacral Plexus")]
    ),
    "Distal Lower Extremity": (
        [skin_entry] +
        [r for r in SBRT_BODY if r["OAR"] in ("Cortical Bone", "Articular Cartilage")]
    ),
}

# ——— Streamlit Session State ———
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "custom_ab" not in st.session_state:
    st.session_state.custom_ab = {}

# ——— Main UI ———
st.title("Re‑irradiation EQD₂ & Palliative OAR Constraints")
tab1, tab2 = st.tabs(["Re‑irradiation EQD₂", "Palliative OAR Constraints"])

# ───────────────────────────── Tab 1: EQD₂ calculator ────────────────────
with tab1:
    # ------------------ INPUT stage --------------------------------------
    if st.session_state.stage == "input":
        selected = st.multiselect("Select OAR(s)", OARS)
        prior_data = {}
        for oar in selected:
            st.subheader(oar)
            ctype = OAR_CONSTRAINTS[oar][0]["type"]
            n_courses = st.selectbox(f"How many prior courses for {oar}?",
                                     [1, 2, 3], key=f"{oar}_nc")
            courses = []
            for i in range(1, n_courses + 1):
                dose = st.number_input(f"Course {i} {ctype} dose (Gy)",
                                       min_value=0.0, step=0.1,
                                       key=f"{oar}_dose{i}")
                fx   = st.number_input(f"Course {i} fractions",
                                       min_value=1, step=1,
                                       key=f"{oar}_fx{i}")
                interval = st.selectbox(f"Time since course {i}",
                                        RECOVERY_FACTORS.keys(),
                                        key=f"{oar}_int{i}")
                if dose and fx:
                    courses.append({"dose": dose,
                                    "fractions": int(fx),
                                    "interval": interval})
            prior_data[oar] = courses

        # optional α/β overrides
        override_ab = {}
        if selected:
            st.subheader("Optional α/β overrides")
            for oar in selected:
                default = OAR_ALPHA_BETA[oar]
                override_ab[oar] = st.number_input(
                    f"{oar} α/β (Gy)", value=float(default),
                    min_value=0.1, step=0.1, key=f"{oar}_ab")

        if st.button("Calculate"):
            st.session_state.selected   = selected
            st.session_state.prior_data = prior_data
            st.session_state.custom_ab  = override_ab
            st.session_state.stage      = "results"
            st.experimental_rerun()

    # ------------------ RESULTS stage ------------------------------------
    elif st.session_state.stage == "results":
        selected   = st.session_state.selected
        prior_data = st.session_state.prior_data

        report = {}
        for oar, courses in prior_data.items():
            ab = st.session_state.custom_ab.get(oar, OAR_ALPHA_BETA[oar])
            raw_sum = eff_sum = 0.0
            for crs in courses:
                n, d = crs["fractions"], crs["dose"]
                eqd   = eqd2(n, d / n, ab)
                raw_sum += eqd
                eff_sum += eqd * (1 - RECOVERY_FACTORS[crs["interval"]])
            limit     = OAR_CONSTRAINTS[oar][0]["value"]
            remaining = max(limit - eff_sum, 0.0)
            report[oar] = dict(limit=limit, raw=raw_sum, eff=eff_sum,
                               recov=raw_sum - eff_sum, left=remaining, ab=ab)

        st.header("Results")
        for oar, r in report.items():
            with st.expander(oar, expanded=True):
                st.write(f"- Hard EQD₂ max: **{r['limit']:.1f} Gy**")
                st.write(f"- Sum raw EQD₂: **{r['raw']:.1f} Gy**")
                st.write(f"- Total recovered: **{r['recov']:.1f} Gy**")
                st.write(f"- Effective prior EQD₂: **{r['eff']:.1f} Gy**")
                st.write(f"- Remaining room: **{r['left']:.1f} Gy**")
                st.info(f"α/β used: **{r['ab']} Gy**")
                st.success(f"→ New EQD₂ max: {r['left']:.1f} Gy")
                lines = ["**Permissible regimens:**"]
                for nfx in FRACTION_OPTIONS:
                    d = max_d_per_fraction(nfx, r["left"], r["ab"])
                    lines.append(f"- {nfx} fx: {d*nfx:.1f} Gy (*{d:.2f} Gy/fx*)")
                st.markdown("\n".join(lines))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back"):
                st.session_state.stage = "input"
                st.experimental_rerun()
        with c2:
            if st.button("Edit α/β"):
                st.session_state.stage = "edit_ab"
                st.experimental_rerun()

    # ------------------ EDIT stage ---------------------------------------
    elif st.session_state.stage == "edit_ab":
        st.header("Override α/β ratios")
        new_ab = {}
        for oar in st.session_state.selected:
            cur = st.session_state.custom_ab.get(oar, OAR_ALPHA_BETA[oar])
            new_ab[oar] = st.number_input(f"{oar} α/β (Gy)",
                                          value=float(cur),
                                          min_value=0.1, step=0.1,
                                          key=f"newab_{oar}")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Cancel"):
                st.session_state.stage = "results"
                st.experimental_rerun()
        with c2:
            if st.button("Apply"):
                st.session_state.custom_ab = new_ab
                st.session_state.stage = "results"
                st.experimental_rerun()

# ───────────────────────── Tab 2: Palliative constraints ──────────────────
with tab2:
    st.header("Palliative OAR Constraints")
    modality = st.radio("Select modality", ["3D", "SBRT"])

    # ------------------ 3D branch ----------------------------------------
    if modality == "3D":
        regimen_map = {
            "8 Gy × 1":   (1,  8.0),
            "20 Gy × 5":  (5, 20.0),
            "24 Gy × 6":  (6, 24.0),
            "30 Gy × 10": (10, 30.0),
            "35 Gy × 10": (10, 35.0),
        }
        choice = st.selectbox("Regimen", regimen_map.keys())
        n_fx, rx_dose = regimen_map[choice]
        cap_val = rx_dose * 1.05

        sites = st.multiselect("Body site(s)", THREED_CONSTRAINTS.keys())
        if not sites:
            st.info("Select at least one body site.")
        else:
            def adjust(txt: str, ab: float) -> str | None:
                if not txt:
                    return None
                out = txt

                def repl(m, sym):
                    eq = float(m.group(1))
                    phys = max_d_per_fraction(n_fx, eq, ab) * n_fx
                    return f"{sym} {phys:.2f} Gy"

                out = re.sub(r"<\s*([\d.]+)\s*Gy", lambda m: repl(m, "<"), out)
                out = re.sub(r"≤\s*([\d.]+)\s*Gy", lambda m: repl(m, "≤"), out)
                out = re.sub(r"≥\s*([\d.]+)\s*Gy", lambda m: repl(m, "≥"), out)
                out = re.sub(r"\\bV\\s*([\\d.]+)\\s*Gy",
                             lambda m: repl(m, f\"V\"), out)
                out = re.sub(r"0\\.03 cc ([\\d.]+) Gy",
                             lambda m: f\"0.03 cc {max_d_per_fraction(n_fx, float(m.group(1)), ab)*n_fx:.2f} Gy\", out)
                out = re.sub(r\"(Max(?: [^0-9<≥]+)*)\\s*([\\d.]+)\\s*Gy\",
                             lambda m: f\"{m.group(1).strip()} {max_d_per_fraction(n_fx, float(m.group(2)), ab)*n_fx:.2f} Gy\", out)
                out = re.sub(r\"([\\d.]+) Gy\",
                             lambda m: f\"{cap_val:.2f} Gy or 105 % Rx\" if float(m.group(1)) > cap_val else m.group(0),
                             out)
                return out

            agg = {}
            for site in sites:
                for row in THREED_CONSTRAINTS[site]:
                    oar = row["OAR"]
                    if oar not in agg:
                        agg[oar] = {"OAR": oar, "Plan Specific Constraints": ""}
                    ab = OAR_ALPHA_BETA.get(oar, 3)
                    p = adjust(row["Preferred"],  ab)
                    a = adjust(row["Acceptable"], ab)
                    parts = []
                    if p: parts.append(f"Preferred: {p}")
                    if a: parts.append(f"Acceptable: {a}")
                    agg[oar]["Plan Specific Constraints"] = " -- ".join(parts)

            df3d_disp = pd.DataFrame(agg.values()).reset_index(drop=True)
            st.subheader("3D‑CRT constraints")
            st.dataframe(df3d_disp, use_container_width=True)

            clip3d = "\\n".join(f"{r.OAR}: {r['Plan Specific Constraints']}"
                                for _, r in df3d_disp.iterrows())
            components.html(
                f\"\"\"\n                <button style='margin-top:10px'\n                        onclick=\"navigator.clipboard.writeText(`{clip3d}`)\">\n                    Copy to clipboard\n                </button>\n                \"\"\", height=40)

    # ------------------ SBRT branch --------------------------------------
    else:
        sites = st.multiselect("Body site(s)", SBRT_CONSTRAINTS.keys())
        fx = st.selectbox("Fractionation", [3, 5])
        if not sites:
            st.info("Select at least one body site.")
        else:
            agg = {}
            for site in sites:
                for r in SBRT_CONSTRAINTS[site]:
                    if fx == 3 and r["OAR"] in EXCLUDE_3FX:
                        continue
                    key = (r["OAR"], r.get("Metric"))
                    if key not in agg:
                        agg[key] = {"OAR": r["OAR"],
                                    "Metric": r.get("Metric"),
                                    "Optimal": None,
                                    "Mandatory": None,
                                    "Endpoint": r.get("Endpoint")}
                    if (opt := r.get(f"{fx}fx_opt")) is not None:
                        agg[key]["Optimal"] = opt
                    if (man := r.get(f"{fx}fx_man")) is not None:
                        agg[key]["Mandatory"] = man

            dfsbrt_disp = pd.DataFrame(agg.values()).reset_index(drop=True)
            st.subheader(f"Combined {fx}-fraction SBRT constraints")
            st.dataframe(dfsbrt_disp, use_container_width=True)

            # clipboard string (skip NaNs)
            lines = []
            for r in dfsbrt_disp.itertuples():
                parts = [r.OAR]
                if r.Metric: parts.append(f"({r.Metric})")
                if pd.notna(r.Optimal):   parts.append(f"Optimal: {r.Optimal}")
                if pd.notna(r.Mandatory): parts.append(f"Mandatory: {r.Mandatory}")
                if r.Endpoint:            parts.append(f"Endpoint: {r.Endpoint}")
                lines.append(" — ".join(parts))

            clip_sbrt = "\\n".join(lines).replace("`", "\\`")
            components.html(
                f\"\"\"\n                <button style='margin-top:10px'\n                        onclick=\"navigator.clipboard.writeText(`{clip_sbrt}`)\">\n                    Copy to clipboard\n                </button>\n                \"\"\", height=40)
