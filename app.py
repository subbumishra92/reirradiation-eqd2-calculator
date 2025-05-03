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

# OARs to hide in 3‑fx SBRT
EXCLUDE_3FX = {"Skin", "Cortical Bone", "Articular Cartilage"}

# ——— Radiobiology Utils ———
def bed(n, d, αβ):
    return n * d * (1 + d/αβ)

def eqd2(n, d, αβ):
    return bed(n, d, αβ) / (1 + 2/αβ)

def max_d_per_fraction(n, target_eqd2, αβ):
    tb = target_eqd2 * (1 + 2/αβ)
    a, b, c = n/αβ, n, -tb
    disc = b*b - 4*a*c
    if disc < 0: return 0.0
    d1 = (-b + math.sqrt(disc)) / (2*a)
    d2 = (-b - math.sqrt(disc)) / (2*a)
    return max(d1, d2)

# ——— 3D‑CRT Palliative Constraints ———
THREED_CONSTRAINTS = {
    "Head and Neck": [
        {"OAR":"Brainstem",      "Preferred":"Max < 55 Gy",                   "Acceptable":"Max (0.03 cc) 60 Gy"},
        {"OAR":"Optic Chiasm",   "Preferred":"Max < 54 Gy",                   "Acceptable":"Max (0.03 cc) 56 Gy"},
        {"OAR":"Optic Nerve",    "Preferred":"Max < 50 Gy",                   "Acceptable":"Max (0.03 cc) 55 Gy"},
        {"OAR":"Cochlea",        "Preferred":"V₅₅ < 5 %",                    "Acceptable":"Mean < 45 Gy"},
        {"OAR":"Retina",         "Preferred":"Max < 45 Gy",                   "Acceptable":"Max < 50 Gy"},
        {"OAR":"Lacrimal Gland", "Preferred":None,                             "Acceptable":"Mean < 26 Gy"},
        {"OAR":"Whole Brain",    "Preferred":None,                             "Acceptable":"Minimize volume ≥ 30 Gy"},
        {"OAR":"Esophagus",      "Preferred":None,                             "Acceptable":"Mean < 30 Gy, no hot spots"},
        {"OAR":"Parotid Glands", "Preferred":None,                             "Acceptable":"Mean < 26 Gy, no hot spots"},
        {"OAR":"Thyroid Gland",  "Preferred":None,                             "Acceptable":"Mean < 37 Gy, no hot spots"},
        {"OAR":"Oral Cavity",    "Preferred":None,                             "Acceptable":"Minimize volume ≥ 30 Gy"},
        {"OAR":"Spinal Cord",    "Preferred":None,                             "Acceptable":"As low as possible; ≤ 105 % Rx"},
        {"OAR":"Skin",           "Preferred":None,                             "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose", "Preferred":"< 105 %",                        "Acceptable":"< 108 %"},
    ],
    "Thorax": [
        {"OAR":"Lungs",          "Preferred":"V₅ < 42 %",                "Acceptable":"V₂₀ < 37 %, Mean < 20 Gy"},
        {"OAR":"Esophagus",      "Preferred":None,                        "Acceptable":"Mean < 30 Gy, no hot spots"},
        {"OAR":"Brachial Plexus","Preferred":None,                        "Acceptable":"No hot spots"},
        {"OAR":"Heart",          "Preferred":None,                        "Acceptable":"V₆₀ < 33 %"},
        {"OAR":"Great Vessels",  "Preferred":None,                        "Acceptable":"No hot spots"},
        {"OAR":"Trachea",        "Preferred":None,                        "Acceptable":"Mean < 30 Gy"},
        {"OAR":"Chest Wall",     "Preferred":None,                        "Acceptable":"No hot spots"},
        {"OAR":"Spinal Cord",    "Preferred":None,                        "Acceptable":"As low as possible; ≤ 45 Gy"},
        {"OAR":"Skin",           "Preferred":None,                        "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose", "Preferred":"< 105 %",                   "Acceptable":"< 108 %"},
    ],
    "Abdomen": [
        {"OAR":"Small Bowel",   "Preferred":None,                         "Acceptable":"As low as possible; Max 45 Gy or 105 % Rx"},
        {"OAR":"Kidneys",       "Preferred":None,                         "Acceptable":"Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR":"Liver",         "Preferred":None,                         "Acceptable":"As low as possible; 50 % < 30 Gy"},
        {"OAR":"Stomach",       "Preferred":None,                         "Acceptable":"As low as possible; 25 % < 45 Gy or 105 % Rx"},
        {"OAR":"Esophagus",     "Preferred":None,                         "Acceptable":"Mean < 34 Gy; V₆₀ < 10 cc"},
        {"OAR":"Lungs",         "Preferred":None,                         "Acceptable":"V₅ < 42 %; V₂₀ < 37 %, Mean < 20 Gy"},
        {"OAR":"Spinal Cord",   "Preferred":None,                         "Acceptable":"As low as possible; ≤ 45 Gy"},
        {"OAR":"Skin",          "Preferred":None,                         "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",                    "Acceptable":"< 108 %"},
    ],
    "Female Pelvis": [
        {"OAR":"Reproductive Organs","Preferred":None,                  "Acceptable":"V₂₀ < 50 %"},
        {"OAR":"Bladder",            "Preferred":None,                  "Acceptable":"V₅₀ < 35 %, V₄₅ < 35 %"},
        {"OAR":"Small Bowel",        "Preferred":None,                  "Acceptable":"As low as possible"},
        {"OAR":"Large Bowel",        "Preferred":None,                  "Acceptable":"As low as possible"},
        {"OAR":"Kidneys",            "Preferred":None,                  "Acceptable":"Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR":"Ureter",             "Preferred":None,                  "Acceptable":"Dmax < 45 Gy (Stricture)"},
        {"OAR":"Skin",               "Preferred":None,                  "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose",     "Preferred":"< 105 %",             "Acceptable":"< 108 %"},
    ],
    "Male Pelvis": [
        {"OAR":"Reproductive Organs","Preferred":None,                  "Acceptable":"D0.5 cc < 42 Gy"},
        {"OAR":"Bladder",            "Preferred":None,                  "Acceptable":"D0.5 cc < 28.2 Gy"},
        {"OAR":"Small Bowel",        "Preferred":None,                  "Acceptable":"As low as possible"},
        {"OAR":"Large Bowel",        "Preferred":None,                  "Acceptable":"As low as possible"},
        {"OAR":"Kidneys",            "Preferred":None,                  "Acceptable":"Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR":"Ureter",             "Preferred":None,                  "Acceptable":"Dmax < 45 Gy (Stricture)"},
        {"OAR":"Skin",               "Preferred":None,                  "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose",     "Preferred":"< 105 %",             "Acceptable":"< 108 %"},
    ],
    "Proximal Upper Extremity": [
        {"OAR":"Brachial Plexus","Preferred":None,                     "Acceptable":"No hot spots"},
        {"OAR":"Skin",          "Preferred":None,                     "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",                "Acceptable":"< 108 %"},
    ],
    "Distal Upper Extremity": [
        {"OAR":"Skin",          "Preferred":None,                     "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",                "Acceptable":"< 108 %"},
    ],
    "Proximal Lower Extremity": [
        {"OAR":"Skin",          "Preferred":None,                     "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",                "Acceptable":"< 108 %"},
    ],
    "Distal Lower Extremity": [
        {"OAR":"Skin",          "Preferred":None,                     "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",                "Acceptable":"< 108 %"},
    ],
}

# ——— SBRT Intracranial & Body Lists ———
SBRT_INTRACRANIAL = [
    {"OAR":"Optic Pathway","Metric":"D0.1cc","3fx_opt":None,  "3fx_man":15,  "5fx_opt":None, "5fx_man":22.5,"Endpoint":"Optic Neuritis"},
    {"OAR":"Cochlea",       "Metric":"Dmean", "3fx_opt":None,  "3fx_man":17.1,"5fx_opt":None, "5fx_man":25,  "Endpoint":"Hearing Loss"},
    {"OAR":"Brainstem",     "Metric":"D0.1cc","3fx_opt":18,    "3fx_man":23.1,"5fx_opt":23,   "5fx_man":31,  "Endpoint":"Cranial Neuropathy"},
    {"OAR":"Spinal Canal",  "Metric":"D0.1cc","3fx_opt":18,    "3fx_man":21.9,"5fx_opt":23,   "5fx_man":30,  "Endpoint":"Myelitis"},
]
# 5fx Skin only, endpoint Ulceration
skin_entry = {
    "OAR":      "Skin",
    "Metric":   "D0.03 cc / V20 Gy",
    "3fx_opt":  None,
    "3fx_man":  None,
    "5fx_opt":  None,
    "5fx_man":  "Dmax (0.03 cc) ≤ 35 Gy; V20 Gy < 10 cc",
    "Endpoint": "Ulceration"
}
SBRT_INTRACRANIAL.append(skin_entry)

SBRT_BODY = [
    {"OAR":"Brachial Plexus",     "Metric":"D0.5cc","3fx_opt":24,   "3fx_man":26,  "5fx_opt":27,  "5fx_man":29,  "Endpoint":"Neuropathy"},
    {"OAR":"Heart / Pericardium", "Metric":"D0.5cc","3fx_opt":24,   "3fx_man":26,  "5fx_opt":27,  "5fx_man":29,  "Endpoint":"Pericarditis"},
    {"OAR":"Great Vessels",       "Metric":"D0.5cc","3fx_opt":None, "3fx_man":45,  "5fx_opt":None,"5fx_man":53,  "Endpoint":"Aneurysm"},
    {"OAR":"Trachea",             "Metric":"D0.5cc","3fx_opt":30,   "3fx_man":32,  "5fx_opt":32,  "5fx_man":35,  "Endpoint":"Stenosis / Fistula"},
    {"OAR":"Chest Wall",          "Metric":"D0.5cc","3fx_opt":37,   "3fx_man":30,  "5fx_opt":39,  "5fx_man":32,  "Endpoint":"Pain / Fracture"},
    {"OAR":"Lungs",               "Metric":"V20Gy", "3fx_opt":None, "3fx_man":"10%","5fx_opt":None,"5fx_man":"10%","Endpoint":"Pneumonitis"},
    {"OAR":"Esophagus",           "Metric":"D0.5cc","3fx_opt":None, "3fx_man":25.2,"5fx_opt":32,  "5fx_man":34,  "Endpoint":"Stenosis / Fistula"},
    {"OAR":"Stomach",             "Metric":"D5cc",  "3fx_opt":None, "3fx_man":16.5,"5fx_opt":25,  "5fx_man":12,  "Endpoint":"Ulceration / Fistula"},
    {"OAR":"Duodenum",            "Metric":"D5cc",  "3fx_opt":None, "3fx_man":16.5,"5fx_opt":25,  "5fx_man":None,"Endpoint":"Ulceration"},
    {"OAR":"Small Bowel",         "Metric":"D0.5cc","3fx_opt":None, "3fx_man":25.2,"5fx_opt":30,  "5fx_man":35,  "Endpoint":"Enteritis / Obstruction"},
    {"OAR":"Large Bowel",         "Metric":"D0.5cc","3fx_opt":None, "3fx_man":28.2,"5fx_opt":None,"5fx_man":32,  "Endpoint":"Colitis / Fistula"},
    {"OAR":"Rectum",              "Metric":"D0.5cc","3fx_opt":None, "3fx_man":28.2,"5fx_opt":None,"5fx_man":32,  "Endpoint":"Proctitis / Fistula"},
    {"OAR":"Cauda Equina",        "Metric":"D0.1cc","3fx_opt":16,   "3fx_man":14,  "5fx_opt":32,  "5fx_man":30,  "Endpoint":"Neuritis"},
    {"OAR":"Lumbosacral Plexus",  "Metric":"D0.03cc","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"Dmax ≤ 30 Gy","Endpoint":None},
    {"OAR":"Ureter",              "Metric":"Dmax",  "3fx_opt":None, "3fx_man":40,  "5fx_opt":None,"5fx_man":45,  "Endpoint":"Stricture"},
]
# Append skin to all SBRT lists
SBRT_BODY.append(skin_entry)

# ——— SBRT_CONSTRAINTS by site ———
SBRT_CONSTRAINTS = {
    "Head and Neck": (
        SBRT_INTRACRANIAL +
        [r for r in SBRT_BODY if r["OAR"] in ("Esophagus","Brachial Plexus")]
    ),
    "Thorax": [
        r for r in SBRT_BODY
        if r["OAR"] in (
            "Lungs","Esophagus","Brachial Plexus",
            "Heart","Great Vessels",
            "Trachea","Chest Wall","Spinal Canal"
        )
    ],
    "Abdomen": [
        r for r in SBRT_BODY
        if r["OAR"] in (
            "Stomach","Duodenum","Small Bowel",
            "Large Bowel","Kidneys","Ureter",
            "Spinal Canal","Cauda Equina","Lumbosacral Plexus"
        )
    ],
    "Female Pelvis": [
        r for r in SBRT_BODY
        if r["OAR"] in (
            "Bladder","Small Bowel","Large Bowel",
            "Kidneys","Ureter","Cauda Equina","Lumbosacral Plexus"
        )
    ],
    "Male Pelvis": [
        r for r in SBRT_BODY
        if r["OAR"] in (
            "Bladder","Small Bowel","Large Bowel",
            "Kidneys","Ureter","Cauda Equina","Lumbosacral Plexus"
        )
    ],
    "Proximal Upper Extremity": [
        r for r in SBRT_BODY if r["OAR"] == "Brachial Plexus"
    ] + [
        skin_entry,
        {"OAR":"Cortical Bone","Metric":"V25Gy/V30Gy","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"V25 < 50 %; V30 < 35 %","Endpoint":None},
        {"OAR":"Articular Cartilage","Metric":"Dmax","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"Dmax ≤ 35 Gy","Endpoint":None},
    ],
    "Distal Upper Extremity": [
        skin_entry,
        {"OAR":"Cortical Bone","Metric":"V25Gy/V30Gy","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"V25 < 50 %; V30 < 35 %","Endpoint":None},
        {"OAR":"Articular Cartilage","Metric":"Dmax","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"Dmax ≤ 35 Gy","Endpoint":None},
    ],
    "Proximal Lower Extremity": [
        skin_entry,
        {"OAR":"Cortical Bone","Metric":"V25Gy/V30Gy","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"V25 < 50 %; V30 < 35 %","Endpoint":None},
        {"OAR":"Articular Cartilage","Metric":"Dmax","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"Dmax ≤ 35 Gy","Endpoint":None},
        {"OAR":"Lumbosacral Plexus","Metric":"D0.03cc","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"Dmax ≤ 30 Gy","Endpoint":None},
    ],
    "Distal Lower Extremity": [
        skin_entry,
        {"OAR":"Cortical Bone","Metric":"V25Gy/V30Gy","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"V25 < 50 %; V30 < 35 %","Endpoint":None},
        {"OAR":"Articular Cartilage","Metric":"Dmax","3fx_opt":None,"3fx_man":None,"5fx_opt":None,"5fx_man":"Dmax ≤ 35 Gy","Endpoint":None},
    ],
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

# ─── Tab 1: EQD₂ Calculator ───────────────────────────────────────────────────
with tab1:
    if st.session_state.stage == "input":
        selected = st.multiselect("Select OAR(s)", OARS)
        prior_data = {}
        for o in selected:
            st.subheader(o)
            ctype = OAR_CONSTRAINTS[o][0]["type"]
            n_courses = st.selectbox(f"How many prior courses for {o}?", [1,2,3], key=f"{o}_nc")
            courses = []
            for i in range(1, n_courses+1):
                dose = st.number_input(f"Course {i} {ctype} dose (Gy)", min_value=0.0, step=0.1, key=f"{o}_d{i}")
                fx   = st.number_input(f"Course {i} fractions", min_value=1, step=1, key=f"{o}_f{i}")
                interval = st.selectbox(f"Time since course {i} to now", list(RECOVERY_FACTORS.keys()), key=f"{o}_int{i}")
                if dose>0 and fx>0:
                    courses.append({"dose":dose,"fractions":int(fx),"interval":interval})
            prior_data[o] = courses

        override_ab = {}
        if selected:
            st.subheader("Optional: override α/β values")
            for o in selected:
                default_ab = OAR_ALPHA_BETA[o]
                override_ab[o] = st.number_input(f"{o} α/β (Gy)", min_value=0.1, step=0.1, value=float(default_ab), key=f"{o}_ab")

        if st.button("Calculate"):
            st.session_state.selected   = selected
            st.session_state.prior_data = prior_data
            st.session_state.custom_ab  = override_ab.copy()
            st.session_state.stage      = "results"
            st.rerun()

    elif st.session_state.stage == "results":
        selected    = st.session_state.selected
        prior_data  = st.session_state.prior_data

        report = {}
        for o, courses in prior_data.items():
            ab = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
            raw_sum = 0.0
            eff_sum = 0.0
            for cr in courses:
                n, dose, interval = cr["fractions"], cr["dose"], cr["interval"]
                eqv = eqd2(n, dose/n, ab)
                raw_sum += eqv
                f = RECOVERY_FACTORS[interval]
                eff_sum += eqv * (1 - f)
            limit    = OAR_CONSTRAINTS[o][0]["value"]
            remaining= max(limit - eff_sum, 0.0)
            report[o] = {"raw_sum":raw_sum,"effective":eff_sum,"recovered":raw_sum-eff_sum,"limit":limit,"remaining":remaining,"ab":ab}

        st.header("Results")
        for o,stt in report.items():
            with st.expander(o, expanded=True):
                st.write(f"- Hard EQD₂ max: **{stt['limit']:.1f} Gy**")
                st.write(f"- Sum raw EQD₂: **{stt['raw_sum']:.1f} Gy**")
                st.write(f"- Total recovered: **{stt['recovered']:.1f} Gy**")
                st.write(f"- Effective prior EQD₂: **{stt['effective']:.1f} Gy**")
                st.write(f"- Remaining room: **{stt['remaining']:.1f} Gy**")
                st.info(f"α/β used for {o}: **{stt['ab']} Gy**")
                st.success(f"→ New EQD₂ max: {stt['remaining']:.1f} Gy")
                lines = ["**Permissible regimens:**"]
                for n in FRACTION_OPTIONS:
                    d = max_d_per_fraction(n, stt["remaining"], stt["ab"])
                    lines.append(f"- {n} fx: {d*n:.1f} Gy (*{d:.2f} Gy/fx*)")
                st.markdown("\n".join(lines))

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
            cur = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
            val = st.number_input(f"{o} α/β (Gy)", min_value=0.1, step=0.1, value=float(cur), key=f"edit_ab_{o}")
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

# ─── Tab 2: Palliative OAR Constraints ───────────────────────────────────────
with tab2:
    st.header("Palliative OAR Constraints")
    modality = st.radio("Select modality", ["3D", "SBRT"])
    selected_sites = st.multiselect("Select body site(s)", list(THREED_CONSTRAINTS.keys()))

    if modality == "3D":
        if not selected_sites:
            st.info("Select at least one body site.")
        else:
            agg = {}
            for site in selected_sites:
                for row in THREED_CONSTRAINTS[site]:
                    o = row["OAR"]
                    if o not in agg:
                        agg[o] = {"OAR":o,"Preferred":None,"Acceptable":None}
                    if row["Preferred"]:
                        agg[o]["Preferred"] = row["Preferred"]
                    if row["Acceptable"]:
                        agg[o]["Acceptable"] = row["Acceptable"]
            df3d = pd.DataFrame(agg.values())
            st.subheader("Combined 3D‑CRT constraints")
            st.dataframe(df3d, use_container_width=True)
            lines = []
            for r in df3d.itertuples():
                lines.append(f"{r.OAR}:")
                if r.Preferred: lines.append(f"  Preferred: {r.Preferred}")
                if r.Acceptable: lines.append(f"  Acceptable: {r.Acceptable}")
                lines.append("")
            st.text_area("Copyable constraints", "\n".join(lines), height=200)

    else:  # SBRT
        fx = st.selectbox("Select fractionation", [3, 5])
        if not selected_sites:
            st.info("Select at least one body site.")
        else:
            agg = {}
            for site in selected_sites:
                for r in SBRT_CONSTRAINTS.get(site, []):
                    # skip unwanted for 3fx
                    if fx == 3 and r["OAR"] in EXCLUDE_3FX:
                        continue
                    key = (r["OAR"], r.get("Metric"))
                    if key not in agg:
                        agg[key] = {
                            "OAR":       r["OAR"],
                            "Metric":    r.get("Metric"),
                            "Optimal":   None,
                            "Mandatory": None,
                            "Endpoint":  r.get("Endpoint")
                        }
                    opt = r.get(f"{fx}fx_opt")
                    man = r.get(f"{fx}fx_man")
                    if opt is not None:
                        agg[key]["Optimal"] = opt
                    if man is not None:
                        agg[key]["Mandatory"] = man

            dfsbrt = pd.DataFrame(agg.values())
            st.subheader(f"Combined {fx}‑fraction SBRT constraints")
            st.dataframe(dfsbrt, use_container_width=True)

            lines = []
            for r in dfsbrt.itertuples():
                parts = [r.OAR]
                if r.Metric: parts.append(f"({r.Metric})")
                if r.Optimal is not None: parts.append(f"Opt: {r.Optimal}")
                if r.Mandatory is not None: parts.append(f"Man: {r.Mandatory}")
                if r.Endpoint: parts.append(f"Endpoint: {r.Endpoint}")
                lines.append(" — ".join(parts))
            st.text_area("Copyable constraints", "\n".join(lines), height=200)
