import streamlit as st
import pandas as pd
import math

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


# ——— Radiobiology Utils ———
def bed(n, d, αβ):
    return n * d * (1 + d/αβ)

def eqd2(n, d, αβ):
    return bed(n, d, αβ) / (1 + 2/αβ)

def max_d_per_fraction(n, target_eqd2, αβ):
    tb = target_eqd2 * (1 + 2/αβ)
    a, b, c = n/αβ, n, -tb
    disc = b*b - 4*a*c
    if disc < 0:
        return 0.0
    d1 = (-b + math.sqrt(disc)) / (2*a)
    d2 = (-b - math.sqrt(disc)) / (2*a)
    return max(d1, d2)


# ——— 3D‑CRT Palliative Constraints ———
THREED_CONSTRAINTS = {
    "Head and Neck": [
        {"OAR":"Brainstem",       "Preferred":"Max < 55 Gy",                   "Acceptable":"Max (0.03 cc) 60 Gy"},
        {"OAR":"Optic Chiasm",    "Preferred":"Max < 54 Gy",                   "Acceptable":"Max (0.03 cc) 56 Gy"},
        {"OAR":"Optic Nerve",     "Preferred":"Max < 50 Gy",                   "Acceptable":"Max (0.03 cc) 55 Gy"},
        {"OAR":"Cochlea",         "Preferred":"V₅₅ < 5 %",                    "Acceptable":"Mean < 45 Gy"},
        {"OAR":"Retina",          "Preferred":"Max < 45 Gy",                   "Acceptable":"Max < 50 Gy"},
        {"OAR":"Lacrimal Gland",  "Preferred":None,                             "Acceptable":"Mean < 26 Gy"},
        {"OAR":"Whole Brain",     "Preferred":None,                             "Acceptable":"Minimize volume ≥ 30 Gy"},
        {"OAR":"Esophagus",       "Preferred":None,                             "Acceptable":"Mean < 30 Gy, no hot spots"},
        {"OAR":"Parotid Glands",  "Preferred":None,                             "Acceptable":"Mean < 26 Gy, no hot spots"},
        {"OAR":"Thyroid Gland",   "Preferred":None,                             "Acceptable":"Mean < 37 Gy, no hot spots"},
        {"OAR":"Oral Cavity",     "Preferred":None,                             "Acceptable":"Minimize volume ≥ 30 Gy"},
        {"OAR":"Spinal Cord",     "Preferred":None,                             "Acceptable":"As low as possible; ≤ 105 % Rx"},
        {"OAR":"Skin",            "Preferred":None,                             "Acceptable":"Dmax <107%"},
        {"OAR":"Max Point Dose",  "Preferred":"< 105 %",                        "Acceptable":"< 108 %"},
    ],
    "Thorax": [
        {"OAR":"Lungs",               "Preferred":"V₅ < 42 %",               "Acceptable":"V₂₀ < 37 %, Mean < 20 Gy"},
        {"OAR":"Esophagus",           "Preferred":None,                       "Acceptable":"Mean < 30 Gy, no hot spots"},
        {"OAR":"Brachial Plexus",     "Preferred":None,                       "Acceptable":"No hot spots"},
        {"OAR":"Heart / Pericardium", "Preferred":None,                       "Acceptable":"V₆₀ < 33 %"},
        {"OAR":"Great Vessels",       "Preferred":None,                       "Acceptable":"No hot spots"},
        {"OAR":"Trachea & Large Bronchi","Preferred":None,                     "Acceptable":"Mean < 30 Gy"},
        {"OAR":"Chest Wall",          "Preferred":None,                       "Acceptable":"No hot spots"},
        {"OAR":"Spinal Cord",         "Preferred":None,                       "Acceptable":"As low as possible; ≤ 45 Gy"},
        {"OAR":"Skin",                "Preferred":None,                       "Acceptable":"Dmax <107%"},
        {"OAR":"Max Point Dose",      "Preferred":"< 105 %",                  "Acceptable":"< 108 %"},
    ],
    "Abdomen": [
        {"OAR":"Small Bowel",         "Preferred":None,                       "Acceptable":"As low as possible; max 45 Gy or 105 % Rx"},
        {"OAR":"Kidneys",             "Preferred":None,                       "Acceptable":"Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR":"Liver",               "Preferred":None,                       "Acceptable":"As low as possible; 50 % < 30 Gy"},
        {"OAR":"Stomach",             "Preferred":None,                       "Acceptable":"As low as possible; 25 % < 45 Gy or 105 % Rx"},
        {"OAR":"Esophagus",           "Preferred":None,                       "Acceptable":"Mean < 34 Gy; V₆₀ < 10 cc"},
        {"OAR":"Lungs",               "Preferred":None,                       "Acceptable":"V₅ < 42 %; V₂₀ < 37 %, Mean < 20 Gy"},
        {"OAR":"Spinal Cord",         "Preferred":None,                       "Acceptable":"As low as possible; ≤ 45 Gy"},
        {"OAR":"Skin",                "Preferred":None,                       "Acceptable":"Dmax <107%"},
        {"OAR":"Max Point Dose",      "Preferred":"< 105 %",                  "Acceptable":"< 108 %"},
    ],
    "Female Pelvis": [
        {"OAR":"Reproductive Organs", "Preferred":None,                       "Acceptable":"V₂₀ Gy < 50 %"},
        {"OAR":"Bladder",             "Preferred":None,                       "Acceptable":"V₅₀ < 35 %, V₄₅ < 35 %"},
        {"OAR":"Small Bowel",         "Preferred":None,                       "Acceptable":"As low as possible"},
        {"OAR":"Large Bowel",         "Preferred":None,                       "Acceptable":"As low as possible"},
        {"OAR":"Kidneys",             "Preferred":None,                       "Acceptable":"Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR":"Ureter",              "Preferred":None,                       "Acceptable":"Dmax < 45 Gy"},
        {"OAR":"Skin",                "Preferred":None,                       "Acceptable":"Dmax <107%"},
        {"OAR":"Max Point Dose",      "Preferred":"< 105 %",                  "Acceptable":"< 108 %"},
    ],
    "Male Pelvis": [
        {"OAR":"Reproductive Organs", "Preferred":None,                       "Acceptable":"D0.5 cc < 42 Gy"},
        {"OAR":"Bladder",             "Preferred":None,                       "Acceptable":"D0.5 cc < 28.2 Gy"},
        {"OAR":"Small Bowel",         "Preferred":None,                       "Acceptable":"As low as possible"},
        {"OAR":"Large Bowel",         "Preferred":None,                       "Acceptable":"As low as possible"},
        {"OAR":"Kidneys",             "Preferred":None,                       "Acceptable":"Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR":"Ureter",              "Preferred":None,                       "Acceptable":"Dmax < 45 Gy"},
        {"OAR":"Skin",                "Preferred":None,                       "Acceptable":"Dmax <107%"},
        {"OAR":"Max Point Dose",      "Preferred":"< 105 %",                  "Acceptable":"< 108 %"},
    ],
    "Proximal Upper Extremity": [
        {"OAR":"Brachial Plexus","Preferred":None,                  "Acceptable":"Optimal 27 Gy; Mandatory 29 Gy"},
        {"OAR":"Skin",           "Preferred":None,                  "Acceptable":"Dmax <107%"},
        {"OAR":"Cortical Bone",  "Preferred":None,                  "Acceptable":"V₂₅ < 50 %; V₃₀ < 35 %"},
        {"OAR":"Articular Cartilage","Preferred":None,              "Acceptable":"Dmax ≤ 35 Gy"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",               "Acceptable":"< 108 %"},
    ],
    "Distal Upper Extremity": [
        {"OAR":"Skin",           "Preferred":None,                  "Acceptable":"Dmax <107%"},
        {"OAR":"Cortical Bone",  "Preferred":None,                  "Acceptable":"V₂₅ < 50 %; V₃₀ < 35 %"},
        {"OAR":"Articular Cartilage","Preferred":None,              "Acceptable":"Dmax ≤ 35 Gy"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",               "Acceptable":"< 108 %"},
    ],
    "Proximal Lower Extremity": [
        {"OAR":"Skin",           "Preferred":None,                  "Acceptable":"Dmax <107%"},
        {"OAR":"Cortical Bone",  "Preferred":None,                  "Acceptable":"V₂₅ < 50 %; V₃₀ < 35 %"},
        {"OAR":"Articular Cartilage","Preferred":None,              "Acceptable":"Dmax ≤ 35 Gy"},
        {"OAR":"Lumbosacral Plexus","Preferred":None,               "Acceptable":"Dmax ≤ 30 Gy"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",               "Acceptable":"< 108 %"},
    ],
    "Distal Lower Extremity": [
        {"OAR":"Skin",           "Preferred":None,                  "Acceptable":"Dmax <107%"},
        {"OAR":"Cortical Bone",  "Preferred":None,                  "Acceptable":"V₂₅ < 50 %; V₃₀ < 35 %"},
        {"OAR":"Articular Cartilage","Preferred":None,              "Acceptable":"Dmax ≤ 35 Gy"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",               "Acceptable":"< 108 %"},
    ],
}

# ——— SBRT Intracranial & Body Lists ———
SBRT_INTRACRANIAL = [
    {"OAR":"Optic Pathway","Metric":"D0.1cc","3fx_opt":None,"3fx_man":15,  "5fx_opt":None,"5fx_man":22.5,"Endpoint":"Optic Neuritis"},
    {"OAR":"Cochlea","Metric":"Dmean","3fx_opt":None,"3fx_man":17.1,        "5fx_opt":None,"5fx_man":25,  "Endpoint":"Hearing Loss"},
    {"OAR":"Brainstem","Metric":"D0.1cc","3fx_opt":18,"3fx_man":23.1,        "5fx_opt":23,  "5fx_man":31,  "Endpoint":"Cranial Neuropathy"},
    {"OAR":"Spinal Canal","Metric":"D0.1cc","3fx_opt":18,"3fx_man":21.9,     "5fx_opt":23,  "5fx_man":30,  "Endpoint":"Myelitis"},
SBRT_INTRACRANIAL.append({
    "OAR":       "Skin",
    "Metric":    "D0.03 cc / V20 Gy",
    "3fx_opt":   None,
    "3fx_man":   None,
    "5fx_opt":   None,
    "5fx_man":   "Dmax (0.03 cc) ≤ 35 Gy; V20 Gy < 10 cc",
    "Endpoint":  None
})
]

SBRT_BODY = [
    {"OAR":"Brachial Plexus","Metric":"D0.5cc","3fx_opt":24, "3fx_man":26, "5fx_opt":27, "5fx_man":29,"Endpoint":"Neuropathy"},
    {"OAR":"Heart / Pericardium","Metric":"D0.5cc","3fx_opt":24, "3fx_man":26, "5fx_opt":27, "5fx_man":29,"Endpoint":"Pericarditis"},
    {"OAR":"Great Vessels","Metric":"D0.5cc","3fx_opt":None,"3fx_man":45,  "5fx_opt":None,"5fx_man":53, "Endpoint":"Aneurysm"},
    {"OAR":"Trachea & Large Bronchi","Metric":"D0.5cc","3fx_opt":30, "3fx_man":32, "5fx_opt":32, "5fx_man":35,"Endpoint":"Stenosis / Fistula"},
    {"OAR":"Chest Wall","Metric":"D0.5cc","3fx_opt":37, "3fx_man":30, "5fx_opt":39, "5fx_man":32,"Endpoint":"Pain / Fracture"},
    {"OAR":"Lungs","Metric":"V20Gy","3fx_opt":None,"3fx_man":"10%","5fx_opt":None,"5fx_man":"10%","Endpoint":"Pneumonitis"},
    {"OAR":"Esophagus","Metric":"D0.5cc","3fx_opt":None,"3fx_man":25.2,      "5fx_opt":32,  "5fx_man":34,  "Endpoint":"Stenosis / Fistula"},
    {"OAR":"Stomach","Metric":"D5cc","3fx_opt":None,"3fx_man":16.5,         "5fx_opt":25,  "5fx_man":12,  "Endpoint":"Ulceration / Fistula"},
    {"OAR":"Duodenum","Metric":"D5cc","3fx_opt":None,"3fx_man":16.5,        "5fx_opt":25,  "5fx_man":None,"Endpoint":"Ulceration"},
    {"OAR":"Small Bowel","Metric":"D0.5cc","3fx_opt":None,"3fx_man":25.2,   "5fx_opt":30,  "5fx_man":35,  "Endpoint":"Enteritis / Obstruction"},
    {"OAR":"Large Bowel","Metric":"D0.5cc","3fx_opt":None,"3fx_man":28.2,   "5fx_opt":None,"5fx_man":32,  "Endpoint":"Colitis / Fistula"},
    {"OAR":"Rectum","Metric":"D0.5cc","3fx_opt":None,"3fx_man":28.2,        "5fx_opt":None,"5fx_man":32,  "Endpoint":"Proctitis / Fistula"},
    {"OAR":"Common Bile Duct","Metric":"D0.5cc","3fx_opt":50,"3fx_man":None,"5fx_opt":50,"5fx_man":None,"Endpoint":"Stenosis"},
    {"OAR":"Kidneys","Metric":"Dmean","3fx_opt":None,"3fx_man":None,       "5fx_opt":10,  "5fx_man":None,"Endpoint":"Renal Dysfunction"},
    {"OAR":"Solitary Functional Kidney","Metric":"V10Gy","3fx_opt":None,"3fx_man":"10%","5fx_opt":None,"5fx_man":"45%","Endpoint":"Renal Dysfunction"},
    {"OAR":"Penile Bulb","Metric":"D0.5cc","3fx_opt":None,"3fx_man":42,    "5fx_opt":None,"5fx_man":50,  "Endpoint":"Impotence"},
    {"OAR":"Bladder","Metric":"D0.5cc","3fx_opt":None,"3fx_man":28.2,       "5fx_opt":None,"5fx_man":38,  "Endpoint":"Cystitis / Fistula"},
    {"OAR":"Ureter","Metric":"Dmax","3fx_opt":None,"3fx_man":40,           "5fx_opt":None,"5fx_man":45,  "Endpoint":None},
    {"OAR":"Skin","Metric":"D0.5cc","3fx_opt":33,"3fx_man":30,             "5fx_opt":39.5,"5fx_man":36.5,"Endpoint":"Ulceration"},
    {"OAR":"Femoral Head","Metric":"D10cc","3fx_opt":21.9,"3fx_man":None,  "5fx_opt":30,  "5fx_man":None,"Endpoint":"Fracture"},
SBRT_BODY.append({
    "OAR":       "Skin",
    "Metric":    "D0.03 cc / V20 Gy",
    "3fx_opt":   None,
    "3fx_man":   None,
    "5fx_opt":   None,
    "5fx_man":   "Dmax (0.03 cc) ≤ 35 Gy; V20 Gy < 10 cc",
    "Endpoint":  None
})
]

# ——— SBRT_CONSTRAINTS by site ———
SBRT_CONSTRAINTS = {
    "Head and Neck": (
        SBRT_INTRACRANIAL +
        [r for r in SBRT_BODY if r["OAR"] in ("Esophagus", "Brachial Plexus")]
    ),
    "Thorax": [
        r for r in SBRT_BODY
        if r["OAR"] in (
            "Lungs","Esophagus","Brachial Plexus",
            "Heart / Pericardium","Great Vessels",
            "Trachea & Large Bronchi","Chest Wall"
        )
    ],
    "Abdomen": [
        r for r in SBRT_BODY
        if r["OAR"] in (
            "Stomach","Duodenum","Small Bowel",
            "Large Bowel","Liver","Kidneys",
            "Common Bile Duct","Ureter"
        )
    ],
    "Female Pelvis": [
        r for r in SBRT_BODY
        if r["OAR"] in ("Bladder","Small Bowel","Large Bowel","Kidneys","Ureter")
    ],
    "Male Pelvis": [
        r for r in SBRT_BODY
        if r["OAR"] in ("Bladder","Small Bowel","Large Bowel","Kidneys","Ureter")
    ],
    "Proximal Upper Extremity": [
        r for r in SBRT_BODY if r["OAR"] == "Brachial Plexus"
    ],
    "Distal Upper Extremity": [],
    "Proximal Lower Extremity": [],
    "Distal Lower Extremity": [],
}

# ——— Session State Flags ———
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "custom_ab" not in st.session_state:
    st.session_state.custom_ab = {}

# ——— Main UI ———
st.title("Re‑irradiation EQD₂ & Palliative OAR Constraints")

tab1, tab2 = st.tabs([
    "Re‑irradiation EQD₂",
    "Palliative OAR Constraints",
])

# ─── Tab 1: EQD₂ Calculator ──────────────────────────────────────────────────
with tab1:
    if st.session_state.stage == "input":
        selected = st.multiselect("Select OAR(s)", OARS)
        global_interval = st.selectbox(
            "Time since last RT to now",
            list(RECOVERY_FACTORS.keys())
        )

        prior_data = {}
        for o in selected:
            st.subheader(o)
            ctype = OAR_CONSTRAINTS[o][0]["type"]
            n_courses = st.selectbox(
                f"How many prior courses for {o}?",
                [1, 2, 3],
                key=f"{o}_nc"
            )
            courses = []
            for i in range(1, n_courses+1):
                dose = st.number_input(
                    f"Course {i} {ctype} dose (Gy)",
                    min_value=0.0, step=0.1, key=f"{o}_d{i}"
                )
                fx = st.number_input(
                    f"Course {i} fractions",
                    min_value=1, step=1, key=f"{o}_f{i}"
                )
                interval = st.selectbox(
                    f"Time since course {i} to now",
                    list(RECOVERY_FACTORS.keys()),
                    key=f"{o}_int{i}"
                )
                if dose > 0 and fx > 0:
                    courses.append({
                        "dose": dose,
                        "fractions": int(fx),
                        "interval": interval
                    })
            prior_data[o] = courses

        override_ab = {}
        if selected:
            st.subheader("Optional: override α/β values")
            for o in selected:
                default_ab = OAR_ALPHA_BETA[o]
                override_ab[o] = st.number_input(
                    f"{o} α/β (Gy)",
                    min_value=0.1, step=0.1,
                    value=float(default_ab),
                    key=f"{o}_ab"
                )

        if st.button("Calculate"):
            st.session_state.selected        = selected
            st.session_state.global_interval = global_interval
            st.session_state.prior_data      = prior_data
            st.session_state.custom_ab       = override_ab.copy()
            st.session_state.stage           = "results"
            st.rerun()

    elif st.session_state.stage == "results":
        selected        = st.session_state.selected
        global_interval = st.session_state.global_interval
        prior_data      = st.session_state.prior_data

        report = {}
        for o, courses in prior_data.items():
            ab = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
            raw_sum = 0.0
            effective_sum = 0.0
            for cr in courses:
                n, dose, interval = cr["fractions"], cr["dose"], cr["interval"]
                eq_val = eqd2(n, dose/n, ab)
                raw_sum += eq_val
                f = RECOVERY_FACTORS[interval]
                effective_sum += eq_val * (1 - f)

            limit    = OAR_CONSTRAINTS[o][0]["value"]
            remaining= max(limit - effective_sum, 0.0)
            report[o] = {
                "raw_sum":   raw_sum,
                "effective": effective_sum,
                "recovered": raw_sum - effective_sum,
                "limit":     limit,
                "remaining": remaining,
                "ab":        ab
            }

        st.header("Results")
        for o, stt in report.items():
            with st.expander(o, expanded=True):
                st.write(f"- Hard EQD₂ max: **{stt['limit']:.1f} Gy**")
                st.write(f"- Sum raw EQD₂: **{stt['raw_sum']:.1f} Gy**")
                st.write(f"- Total recovered: **{stt['recovered']:.1f} Gy**")
                st.write(f"- Effective prior EQD₂: **{stt['effective']:.1f} Gy**")
                st.write(f"- Remaining room: **{stt['remaining']:.1f} Gy**")
                st.info(f"α/β used for {o}: **{stt['ab']} Gy**")
                st.success(f"→ New EQD₂ max: {stt['remaining']:.1f} Gy")

                md = ["**Permissible regimens:**"]
                for n in FRACTION_OPTIONS:
                    d = max_d_per_fraction(n, stt["remaining"], stt["ab"])
                    md.append(f"- {n} fx: {d*n:.1f} Gy (*{d:.2f} Gy/fx*)")
                st.markdown("\n".join(md))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back to inputs"):
                st.session_state.stage = "input"
                st.rerun()
        with c2:
            if st.button("Edit α/β"):
                st.session_state.stage = "edit_ab"
                st.rerun()

    elif st.session_state.stage == "edit_ab":
        st.header("Override α/β ratios")
        new_ab = {}
        for o in st.session_state.selected:
            current_ab = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
            val = st.number_input(
                f"{o} α/β (Gy)",
                min_value=0.1, step=0.1,
                value=float(current_ab),
                key=f"edit_ab_{o}"
            )
            new_ab[o] = val

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Cancel"):
                st.session_state.stage = "results"
                st.rerun()
        with c2:
            if st.button("Apply and Recalculate"):
                st.session_state.custom_ab = new_ab.copy()
                st.session_state.stage     = "results"
                st.rerun()

# ─── Tab 2: Palliative OAR Constraints ───────────────────────────────────────
with tab2:
    st.header("Palliative OAR Constraints")

    modality = st.radio("Select modality", ["3D", "SBRT"])
    site     = st.selectbox("Select body site", list(THREED_CONSTRAINTS.keys()))

    if modality == "3D":
        df3d = pd.DataFrame(THREED_CONSTRAINTS[site])
        st.subheader(f"3D‑CRT constraints for {site}")
        st.dataframe(df3d, use_container_width=True)

    else:  # SBRT
        fx = st.selectbox("Select fractionation", [3, 5])
        sb = SBRT_CONSTRAINTS.get(site, [])
        data_sbrt = []
        for r in sb:
            data_sbrt.append({
                "OAR":       r["OAR"],
                "Metric":    r.get("Metric"),
                "Optimal":   r.get(f"{fx}fx_opt"),
                "Mandatory": r.get(f"{fx}fx_man"),
                "Endpoint":  r.get("Endpoint")
            })
        df_sbrt = pd.DataFrame(data_sbrt)
        st.subheader(f"{fx}‑fraction SBRT constraints for {site}")
        st.dataframe(df_sbrt, use_container_width=True)
