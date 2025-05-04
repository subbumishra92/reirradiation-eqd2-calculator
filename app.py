import streamlit as st
import pandas as pd
import math
import re

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
def bed(n, d, αβ): return n * d * (1 + d/αβ)
def eqd2(n, d, αβ): return bed(n, d, αβ) / (1 + 2/αβ)
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
        {"OAR":"Whole Brain",    "Preferred":None,                             "Acceptable":"Minimize volume ≥ 30 Gy"},
        {"OAR":"Esophagus",      "Preferred":None,                             "Acceptable":"Mean < 30 Gy; no hot spots"},
        {"OAR":"Parotid Glands", "Preferred":None,                             "Acceptable":"Mean < 26 Gy; no hot spots"},
        {"OAR":"Thyroid Gland",  "Preferred":None,                             "Acceptable":"Mean < 37 Gy; no hot spots"},
        {"OAR":"Oral Cavity",    "Preferred":None,                             "Acceptable":"Minimize volume ≥ 30 Gy"},
        {"OAR":"Spinal Cord",    "Preferred":None,                             "Acceptable":"As low as possible; ≤ 105 % Rx"},
        {"OAR":"Skin",           "Preferred":None,                             "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose", "Preferred":"< 105 %",                        "Acceptable":"< 108 %"},
    ],
    "Thorax": [
        {"OAR":"Lungs",          "Preferred":"V₅ < 42 %",                    "Acceptable":"V₂₀ < 37 %; Mean < 20 Gy"},
        {"OAR":"Esophagus",      "Preferred":None,                             "Acceptable":"Mean < 30 Gy; no hot spots"},
        {"OAR":"Brachial Plexus","Preferred":None,                             "Acceptable":"No hot spots"},
        {"OAR":"Heart",          "Preferred":None,                             "Acceptable":"V₆₀ < 33 %"},
        {"OAR":"Great Vessels",  "Preferred":None,                             "Acceptable":"No hot spots"},
        {"OAR":"Trachea",        "Preferred":None,                             "Acceptable":"Mean < 30 Gy"},
        {"OAR":"Chest Wall",     "Preferred":None,                             "Acceptable":"No hot spots"},
        {"OAR":"Spinal Cord",    "Preferred":None,                             "Acceptable":"As low as possible; ≤ 45 Gy"},
        {"OAR":"Skin",           "Preferred":None,                             "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose", "Preferred":"< 105 %",                        "Acceptable":"< 108 %"},
    ],
    "Abdomen": [
        {"OAR":"Small Bowel",   "Preferred":None,                             "Acceptable":"As low as possible; Max 45 Gy or 105 % Rx"},
        {"OAR":"Kidneys",       "Preferred":None,                             "Acceptable":"Mean < 15 Gy (or < 9 Gy if solitary)"},
        {"OAR":"Liver",         "Preferred":None,                             "Acceptable":"As low as possible; 50 % < 30 Gy"},
        {"OAR":"Stomach",       "Preferred":None,                             "Acceptable":"As low as possible; 25 % < 45 Gy or 105 % Rx"},
        {"OAR":"Esophagus",     "Preferred":None,                             "Acceptable":"Mean < 34 Gy; V₆₀ < 10 cc"},
        {"OAR":"Lungs",         "Preferred":None,                             "Acceptable":"V₅ < 42 %; V₂₀ < 37 %, Mean < 20 Gy"},
        {"OAR":"Spinal Cord",   "Preferred":None,                             "Acceptable":"As low as possible; ≤ 45 Gy"},
        {"OAR":"Skin",          "Preferred":None,                             "Acceptable":"No slices 100 % circumf.; Hot‑spot < 107 %"},
        {"OAR":"Max Point Dose","Preferred":"< 105 %",                        "Acceptable":"< 108 %"},
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

# ——— Normalize entries for adjust() ———
sub_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
for site, rows in THREED_CONSTRAINTS.items():
    for row in rows:
        for col in ("Preferred", "Acceptable"):
            txt = row[col]
            if not txt: continue
            s = txt.translate(sub_map)
            s = re.sub(r"\s*\(\s*0\.03\s*cc\s*\)\s*", " 0.03 cc ", s)
            s = re.sub(r"\bV\s*([\d\.]+)\s*(?=[<≥])", r"V\1 Gy ", s)
            s = re.sub(r"\s+", " ", s).strip()
            row[col] = s

# ——— SBRT Intracranial & Body Lists ———
SBRT_INTRACRANIAL = [...]
SBRT_BODY = [...]
SBRT_CONSTRAINTS = {...}  # unchanged from previous

# ——— Session State Flags ———
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "custom_ab" not in st.session_state:
    st.session_state.custom_ab = {}

# ——— Main UI ———
st.title("Re‑irradiation EQD₂ & Palliative OAR Constraints")
tab1, tab2 = st.tabs(["Re‑irradiation EQD₂", "Palliative OAR Constraints"])

# Tab 1: re‑irradiation EQD₂ (unchanged)  
# … [omitted for brevity; same as before] …

# ─── Tab 2: Palliative OAR Constraints ───────────────────────────────────────
with tab2:
    st.header("Palliative OAR Constraints")
    modality = st.radio("Select modality", ["3D", "SBRT"])

    if modality == "3D":
        regimen_map = {
            "8 Gy × 1 fx":    (1, 8.0),
            "20 Gy × 5 fx":   (5, 20.0),
            "24 Gy × 6 fx":   (6, 24.0),
            "30 Gy × 10 fx":  (10, 30.0),
            "35 Gy × 10 fx":  (10, 35.0),
        }
        regimen = st.selectbox("Select regimen", list(regimen_map.keys()))
        n_fx, _ = regimen_map[regimen]

        selected_sites = st.multiselect("Select body site(s)", list(THREED_CONSTRAINTS.keys()))
        if not selected_sites:
            st.info("Select at least one body site.")
        else:
            def adjust(txt, ab):
                if not txt: return None
                out = txt
                # < X Gy
                def cap(m):
                    eq = float(m.group(1)); d_phys = max_d_per_fraction(n_fx, eq, ab)
                    return f"< {d_phys*n_fx:.2f} Gy"
                # V X Gy
                def vol(m):
                    eq = float(m.group(1)); d_phys = max_d_per_fraction(n_fx, eq, ab)
                    return f"V{d_phys*n_fx:.2f} Gy"
                # ≥ X Gy
                def ge(m):
                    eq = float(m.group(1)); d_phys = max_d_per_fraction(n_fx, eq, ab)
                    return f"≥ {d_phys*n_fx:.2f} Gy"
                # Max X Gy
                def mx(m):
                    eq = float(m.group(1)); d_phys = max_d_per_fraction(n_fx, eq, ab)
                    return f"Max {d_phys*n_fx:.2f} Gy"

                out = re.sub(r"<\s*([\d\.]+)\s*Gy",       cap, out)
                out = re.sub(r"\bV\s*([\d\.]+)\s*Gy",      vol, out)
                out = re.sub(r"≥\s*([\d\.]+)\s*Gy",        ge,  out)
                out = re.sub(r"Max\s*([\d\.]+)\s*Gy",      mx,  out)
                return out

            agg = {}
            for site in selected_sites:
                for row in THREED_CONSTRAINTS[site]:
                    o = row["OAR"]
                    if o not in agg:
                        agg[o] = {"OAR": o, "Plan Specific Constraints": ""}
                    ab = OAR_ALPHA_BETA.get(o, 3)
                    p = adjust(row["Preferred"], ab) or row["Preferred"] or ""
                    a = adjust(row["Acceptable"], ab) or row["Acceptable"] or ""
                    parts = []
                    if p: parts.append(f"Preferred: {p}")
                    if a: parts.append(f"Acceptable: {a}")
                    agg[o]["Plan Specific Constraints"] = " -- ".join(parts)

            df3d = pd.DataFrame(agg.values())
            st.subheader("3D‑CRT constraints")
            st.dataframe(df3d, use_container_width=True)
            lines = [f"{r.OAR}: {r._2}" for r in df3d.itertuples()]
            st.text_area("Copyable constraints", "\n".join(lines), height=250)

    else:
        # SBRT tab unchanged (unified Pelvis, full labels)  
        # … [omitted for brevity; same as before] …
