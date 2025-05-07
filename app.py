import streamlit as st
import pandas as pd
import math
import re
import streamlit.components.v1 as components
from pathlib import Path
import yaml

# ——— Load all the “other” CORSAIR tables from Experimental_Dose_Constraints.yaml ———
base = Path(__file__).parent

# general adult
with open(base / "CORSAIR_TG101.yaml", "r") as f:
    general_constraints = yaml.safe_load(f)

# the one YAML that actually contains the 4 other tables:
with open(base / "Experimental_Dose_Constraints.yaml", "r") as f:
    all_other = yaml.safe_load(f)

# now extract them by their top‑level keys
experimental_constraints = all_other["Experimental_Dose_Constraints"]
hodgkin_constraints      = all_other["Hodgkin_Lymphoma_Dose_Constraints"]
hypo_constraints         = all_other["Hypofractionated_Breast_Constraints"]
pediatric_constraints    = all_other["Pediatric_Dose_Constraints"]

# ——— Wrap list‑only tables under a ‘conventional’ scheme key ———
for tbl in (experimental_constraints,
            hodgkin_constraints,
            pediatric_constraints):
    for organ, val in list(tbl.items()):
        # if the YAML gave us organ → [ … ], not → { scheme_key: [ … ] }
        if isinstance(val, list):
            tbl[organ] = {"conventional": val}

    
# ——— Page config ———
st.set_page_config(page_title="Palliative Radiotherapy Planning", layout="wide")

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

# ——— REFERENCES DICTIONARY ———
# cleaned to “LastName et al.” style, ready to paste into Python
references = {
    1:  'Rubin & Casarett. "Clinical radiation pathology as applied to curative radiotherapy." Front Radiat. Ther. Oncol. 1968, 22, 767–778.',
    2:  'Emami et al. "Tolerance of Normal Tissue to Therapeutic Irradiation." Int. J. Radiat. Oncol. Biol. Phys. 1991, 21, 109–122.',
    3:  'Marks et al. "Guest Editor’s Introduction to QUANTEC: A Users Guide." Int. J. Radiat. Oncol. Biol. Phys. 2010, 76, S1–S2.',
    4:  'Bentzen et al. "Quantitative Analyses of Normal Tissue Effects in the Clinic (QUANTEC): An Introduction to the Scientific Issues." Int. J. Radiat. Oncol. Biol. Phys. 2010, 76, S3–S9.',
    5:  'Marks et al. "Use of Normal Tissue Complication Probability Models in the Clinic." Int. J. Radiat. Oncol. Biol. Phys. 2010, 76, S10–S19.',
    6:  'Diez et al. "UK 2022 Consensus on Normal Tissue Dose–Volume Constraints for Oligometastatic, Primary Lung and Hepatocellular Carcinoma SABR." Clin. Oncol. 2022, 34, 288–300.',
    7:  'Hanna et al. "UK Consensus on Normal Tissue Dose Constraints for Stereotactic Radiotherapy." Clin. Oncol. 2018, 30, 5–14.',
    8:  'Benedict et al. "Stereotactic Body Radiation Therapy: The Report of AAPM Task Group 101." Med. Phys. 2010, 37, 4078–4101.',
    9:  'Milano et al. "Single‑ and Multifraction Stereotactic Radiosurgery Dose/Volume Tolerances of the Brain." Int. J. Radiat. Oncol. Biol. Phys. 2021, 110, 68–86.',
    10: 'Grimm et al. "Dose Tolerance Limits and Dose–Volume Histogram Evaluation for Stereotactic Body Radiotherapy." J. Appl. Clin. Med. Phys. 2011, 12, 267–292.',
    11: 'NCCN Guidelines et al. "NCCN Clinical Practice Guidelines in Oncology—Hodgkin Lymphoma. Version 1.2023."',
    13: 'Coles et al. "Partial‑Breast Radiotherapy after Breast Conservation Surgery (UK IMPORT LOW): 5‑Year Results." Lancet 2017, 390, 1048–1060.',
    14: 'Meattini et al. "APBI‑IMRT‑Florence Trial: Accelerated Partial‑Breast vs Whole‑Breast Irradiation: Long‑Term Results." J. Clin. Oncol. 2020, 38, 4175–4183.',
    15: 'Murray Brunt et al. "FAST‑Forward Trial: 1 Week vs 3 Weeks Hypofractionation." Lancet 2020, 395, 1613–1626.',
    16: 'Palmer et al. "Late Effects of Radiation Therapy in Pediatric Patients and Survivorship." Pediatr. Blood Cancer 2021, 68, e28349.',
    17: 'Milano et al. "Primary Hypothyroidism in Childhood Cancer Survivors Treated With Radiation Therapy: A PENTEC Review." Int. J. Radiat. Oncol. Biol. Phys. 2021.',
    18: 'Mahajan et al. "Neurocognitive Effects and Necrosis in Childhood Cancer Survivors: A PENTEC Review." Int. J. Radiat. Oncol. Biol. Phys. 2021.',
    20: 'Milgrom et al. "Salivary and Dental Complications in Childhood Cancer Survivors: A PENTEC Review." Int. J. Radiat. Oncol. Biol. Phys. 2021.',
    21: 'Hodgson et al. "ILROG Guidelines for Pediatric Hodgkin Lymphoma RT Planning." Pract. Radiat. Oncol. 2015, 5, 85–92.',
    22: 'Reis et al. "SBRT of Ventricular Tachycardia Using 4π Optimized Trajectories." J. Appl. Clin. Med. Phys. 2021, 22, 72–86.',
    23: 'Blanck et al. "RAVENTA Trial: Feasibility of Radiosurgery for Ventricular Tachycardia." Clin. Res. Cardiol. 2020, 109, 1319–1332.',
    24: 'Chiu et al. "Review of Stereotactic Arrhythmia Radioablation Therapy for Cardiac Tachydysrhythmias." CJC Open 2021, 3, 236–247.',
    25: 'NCCN Guidelines et al. "Non‑Small Cell Lung Cancer v5.2022."',
    26: 'NCCN Guidelines et al. "Esophageal and Esophagogastric Junction Cancers v4.2022."',
    28: 'NCCN Guidelines et al. "Anal Cancer v2.2022."',
    30: 'Dapper et al. "Impact of VMAT‑IMRT vs 3D‑CRT on Anal Sphincter Dose in Rectal Cancer." Radiat. Oncol. 2018, 13, 237.',
    31: 'Jadon et al. "Systematic Review of Dose–Volume Predictors for Late Bowel Toxicity." Radiat. Oncol. 2019, 14, 1–14.',
    32: 'Peng et al. "Dose–Volume Analysis of Predictors for Acute Anal Toxicity in Prostate Cancer." Radiat. Oncol. 2019, 14, 1–9.',
    33: 'Atkins et al. "Association of LAD Coronary Dose with Cardiac Events in NSCLC." JAMA Oncol. 2021, 7, 206–219.',
    34: 'Brodin & Tomé. "Revisiting Dose Constraints for Head & Neck OARs in IMRT Era." Oral Oncol. 2018, 86, 8–18.',
    35: 'Merlotti et al. "Technical Guidelines for H&N IMRT (AIRO‑HN WG)." Radiat. Oncol. 2014, 9, 264.',
    36: 'Brunner et al. "ESTRO ACROP Guidelines for CTV Delineation in Pancreatic Cancer." Radiother. Oncol. 2021, 154, 60–69.',
    37: 'Eekers et al. "EPTN Consensus Atlas for CT/MR Contouring in Neuro‑Oncology." Radiother. Oncol. 2018, 128, 37–43.',
    38: 'Inoue et al. "Three‑Fraction CyberKnife RT for Brain Mets (V14)." J. Radiat. Res. 2013, 54, 727–735.',
    39: 'Niyazi et al. "ESTRO‑ACROP Guideline: Target Delineation of Glioblastomas." Radiother. Oncol. 2016, 118, 35–42.',
    40: 'Scoccianti et al. "OARs in the Brain & Their Dose Constraints in Adults & Children." Radiother. Oncol. 2015, 114, 230–238.',
    41: 'Li et al. "Dosimetric Analysis of Dysphagia & G‑Tube Dependence in H&N IMRT+Chemo." Radiat. Oncol. 2009, 4, 52.',
    42: 'Basu & Bhaskar. "Overview of Important OARs in H&N Cancer RT." In Cancer Survivorship, IntechOpen 2019.',
    43: 'Lambrecht et al. "Dose Constraints for OARs in Neuro‑Oncology: EPTN Consensus." Radiother. Oncol. 2018, 128, 26–36.',
    44: 'Gondi et al. "Hippocampal Dosimetry Predicts Neurocognitive Decline after SRS." Int. J. Radiat. Oncol. Biol. Phys. 2013, 85, 348–354.',
    45: 'Brown et al. "Hippocampal Avoidance WBRT+Memantine for Brain Mets: NRG CC001." J. Clin. Oncol. 2020, 38, 1019–1029.',
    46: 'Pinkham et al. "Hippocampal‑Sparing RT: New Standard for Grade II/III Gliomas?" J. Clin. Neurosci. 2014, 21, 86–90.',
    47: 'Goodman et al. "RTOG Consensus Guidelines: CTV Delineation Postop Pancreatic Head Cancer." Int. J. Radiat. Oncol. Biol. Phys. 2012, 83, 901–908.',
    48: 'Yeoh et al. "Pudendal Nerve Injury Impairs Anorectal Function ≥2 Years Post‑3D‑CRT for Prostate Ca." Acta Oncol. 2018, 57, 456–464.',
    49: 'Kovtun et al. "Ovary‑Sparing RT Techniques for Buttock/Thigh Sarcoma." Sarcoma 2017, 2017, 2796925.',
    50: 'Vyfhuis et al. "Preserving Endocrine Function in Premenopausal Women Receiving Whole‑Pelvis RT." Int. J. Part. Ther. 2019, 6, 10–17.',
    51: 'Du & Qu. "Relationship between Ovarian Function and Dose Post‑Transposition in Young Cervical Ca." Cancer Med. 2017, 6, 508–515.',
    52: 'Polanowski et al. "Analysis of Pancreatic Dose during Gastric Ca RT." Radiother. Oncol. 2020, 151, 20–23.',
    53: 'Gemici et al. "Volumetric Decrease of Pancreas after Abdominal Irradiation." Radiat. Oncol. 2018, 13, 238.',
    54: 'Palmisciano et al. "SBRT in Non‑Operable Lung Ca Patients." Clin. Transl. Oncol. 2016, 18, 1158–1159.',
    55: 'Uehara et al. "Feasibility of VMAT with Halcyon™ for Total Body Irradiation." Radiat. Oncol. 2021, 16, 236.',
    56: 'De Felice et al. "Radiation Effects on Male Fertility." Andrology 2019, 7, 2–7.',
    57: 'Hoskin et al. "GEC/ESTRO Recommendations on HDR Afterloading Brachytherapy for Prostate Ca: Update." Radiother. Oncol. 2013, 107, 325–332.',
    58: 'Henry et al. "GEC‑ESTRO ACROP Prostate Brachytherapy Guidelines." Radiother. Oncol. 2022, 167, 244–251.',
    59: 'Susan. "Anatomy: The Anatomical Basis of Clinical Practice, 2nd ed." Elsevier 2020.',
    60: 'Feng et al. "Development and Validation of a Heart Atlas for Breast Ca RT." Int. J. Radiat. Oncol. Biol. Phys. 2011, 79, 10–18.',
    61: 'Duane et al. "A Cardiac Contouring Atlas for Radiotherapy." Radiother. Oncol. 2017, 122, 416–422.',
    99: 'Bisello et al. “Supplementary Table S1: Emerging OARs.” Curr. Oncol. 2022.',
   100: 'Bisello et al. “Supplementary Table S1: Bichat Fat Pad data.” Curr. Oncol. 2022.',
   101: 'Bisello et al. “Supplementary Table S1: Bone‐Marrow V20Gy < 84%.” Curr. Oncol. 2022.',
   102: 'Bisello et al. “Supplementary Table S1: Bone‐Marrow Dmean constraints.” Curr. Oncol. 2022.',
   103: 'Bisello et al. “Supplementary Table S1: Femur Dmax constraints.” Curr. Oncol. 2022.',
   104: 'Bisello et al. “Supplementary Table S1: Femur Dmax optimal.” Curr. Oncol. 2022.',
   105: 'Bisello et al. “Supplementary Table S1: Hypothalamus Dmax.” Curr. Oncol. 2022.',
   106: 'Bisello et al. “Supplementary Table S1: Vagina D2cc EQD2.” Curr. Oncol. 2022.',
   107: 'Bisello et al. “Supplementary Table S1: Vagina Drectovaginal point.” Curr. Oncol. 2022.',
   108: 'Bisello et al. “Supplementary Table S2: Breast Dmean/V4Gy constraints.” Curr. Oncol. 2022.',
   109: 'Bisello et al. “Supplementary Table S3: Anterior Descending Artery Dmax.” Curr. Oncol. 2022.',
   110: 'Bisello et al. “Supplementary Table S3: Hypofractionation breast Dmax.” Curr. Oncol. 2022.',
   111: 'Bisello et al. “Supplementary Table S3: Lung V20Gy < 10%.” Curr. Oncol. 2022.',
   112: 'Bisello et al. “Supplementary Table S4: Pediatric Brain V necrosis risk.” Curr. Oncol. 2022.',
   113: 'Bisello et al. “Supplementary Table S4: Cochlea Dmean < 35Gy.” Curr. Oncol. 2022.',
   114: 'Bisello et al. “Supplementary Table S4: Heart Dmean/V20Gy.” Curr. Oncol. 2022.',
   115: 'Bisello et al. “Supplementary Table S4: Lung V24Gy < 30%.” Curr. Oncol. 2022.',
   116: 'Bisello et al. “Supplementary Table S4: Brainstem Dmax/V55Gy.” Curr. Oncol. 2022.',
   117: 'Bisello et al. “Supplementary Table S4: Optic Pathway Dmax.” Curr. Oncol. 2022.',
   118: 'Bisello et al. “Supplementary Table S4: Orbital Bone Dmax.” Curr. Oncol. 2022.',
   119: 'Bisello et al. “Supplementary Table S4: Spleen Dmean.” Curr. Oncol. 2022.',
   120: 'Bisello et al. “Supplementary Table S4: Submandibular Gland Dmean.” Curr. Oncol. 2022.',
   121: 'Bisello et al. “Supplementary Table S4: Rectum D5cc EQD2.” Curr. Oncol. 2022.',
}

# ——— Main UI ———
st.title("Palliative Radiotherapy Planning")
tab1, tab2, tab3 = st.tabs([
    "Re‑irradiation Dose Limit Calculator",
    "Palliative Radiotherapy Planning Protocols",
    "OAR Dose Constraints Lookup"
])


# ───────────────────────────── Tab 1: EQD₂ calculator ────────────────────
with tab1:
    st.header("Re‑irradiation Dose Limit Calculator")

    # ——— Basic user instructions ———
    st.info(
        "**How to use this tool:**\n"
        "- Select one or more common dose limiting OARs from the dropdown, or choose **Custom OAR** to define your own.\n"
        "- For each selected OAR, enter:\n"
        "  1. **Max EQD₂ limit** (Gy)\n"
        "  2. **α/β ratio** (Gy)\n"
        "  3. Number of prior courses, and for each course:\n"
        "     - Total dose (Gy)\n"
        "     - Number of fractions\n"
        "     - Expected percent recovery from prior dose (0–100 %)\n"
        "- Click **Calculate** to see remaining EQD₂ room and feasible regimens."
    )

    # ——— INPUT stage ———
    # Put “Custom OAR” first in the list
    all_oars = ["Custom OAR"] + OARS
    selected = st.multiselect(
        "Select OAR(s) or create a custom OAR",
        all_oars
    )

    prior_data      = {}
    limit_overrides = {}
    ab_overrides    = {}

    for oar in selected:
        st.subheader(oar)

        # 1) Max EQD₂ limit override  (0–150 Gy)
        default_limit = (
            OAR_CONSTRAINTS[oar][0]["value"]
            if oar in OAR_CONSTRAINTS and oar != "Custom OAR"
            else 0.0
        )
        limit = st.number_input(
            f"Max EQD₂ limit for {oar} (Gy)",
            min_value=0.0,
            max_value=150.0,
            value=float(default_limit),
            step=0.1,
            key=f"{oar}_limit"
        )
        limit_overrides[oar] = limit

        # 2) α/β override (0.1–100 Gy)
        default_ab = (
            OAR_ALPHA_BETA.get(oar, 3.0)
            if oar != "Custom OAR"
            else 3.0
        )
        ab = st.number_input(
            f"{oar} α/β (Gy)",
            min_value=0.1,
            max_value=100.0,
            value=float(default_ab),
            step=0.1,
            key=f"{oar}_ab"
        )
        ab_overrides[oar] = ab

        # 3) Prior courses
        n_courses = st.number_input(
            f"Number of prior courses for {oar}",
            min_value=0,
            max_value=10,
            value=0,
            step=1,
            key=f"{oar}_nc"
        )

        courses = []
        for i in range(1, int(n_courses) + 1):
            dose = st.number_input(
                f"  Course {i} total dose (Gy)",
                min_value=0.0,
                step=0.1,
                key=f"{oar}_dose{i}"
            )
            fx = st.number_input(
                f"  Course {i} fractions",
                min_value=1,
                step=1,
                key=f"{oar}_fx{i}"
            )
            recov_pct = st.number_input(
                f"  Course {i} % recovery",
                min_value=0,
                max_value=100,
                value=0,
                step=1,
                key=f"{oar}_recov{i}"
            )
            courses.append({
                "dose":      float(dose),
                "fractions": int(fx),
                "recovery":  recov_pct / 100.0
            })

        prior_data[oar] = courses

    # Calculate button
    if st.button("Calculate"):
        st.session_state.prior_data      = prior_data
        st.session_state.limit_overrides = limit_overrides
        st.session_state.ab_overrides    = ab_overrides
        st.session_state.selected        = selected
        st.session_state.stage           = "results"
        st.rerun()

    # ——— RESULTS stage ———
    if st.session_state.get("stage") == "results":
        report = {}
        for oar in st.session_state.selected:
            courses = st.session_state.prior_data[oar]
            ab      = st.session_state.ab_overrides[oar]
            limit   = st.session_state.limit_overrides[oar]

            raw = eff = 0.0
            for c in courses:
                eq = eqd2(c["fractions"], c["dose"]/c["fractions"], ab)
                raw += eq
                eff += eq * (1 - c["recovery"])

            remaining = max(limit - eff, 0.0)
            report[oar] = {
                "limit":     limit,
                "raw":       raw,
                "recovered": raw - eff,
                "eff":       eff,
                "left":      remaining,
                "ab":        ab
            }

        st.header("Results")
        for oar, r in report.items():
            with st.expander(oar, expanded=True):
                st.write(f"- **Max EQD₂ limit:** {r['limit']:.1f} Gy")
                st.write(f"- **Sum raw EQD₂:** {r['raw']:.1f} Gy")
                st.write(f"- **Total recovered:** {r['recovered']:.1f} Gy")
                st.write(f"- **Effective prior EQD₂:** {r['eff']:.1f} Gy")
                st.write(f"- **Remaining room:** {r['left']:.1f} Gy")
                st.info(f"α/β used: {r['ab']:.1f} Gy")

                st.write("**Permissible regimens:**")
                for nfx in FRACTION_OPTIONS:
                    d_per_fx = max_d_per_fraction(nfx, r["left"], r["ab"])
                    total_d  = d_per_fx * nfx
                    st.write(f"- {nfx} fx → {total_d:.1f} Gy ({d_per_fx:.2f} Gy/fx)")

        if st.button("← Back"):
            st.session_state.stage = "input"
            st.rerun()


# ───────────────────────── Tab 2: Palliative constraints ──────────────────
with tab2:
    st.header("Protocol Selection")
    modality = st.radio("Select modality", ["3D", "SBRT"])

    # ------------------ 3D branch ----------------------------------------
    if modality == "3D":
        regimen_map = {
            "8 Gy × 1":  (1,  8.0),
            "20 Gy × 5": (5, 20.0),
            "24 Gy × 6": (6, 24.0),
            "30 Gy × 10": (10, 30.0),
            "35 Gy × 10": (10, 35.0),
        }
        choice = st.selectbox("Regimen", regimen_map.keys())
        n_fx, rx_dose = regimen_map[choice]
        cap_val = rx_dose * 1.05

        sites = st.multiselect("Body site(s)", THREED_CONSTRAINTS.keys())
        if sites:
            def adjust(txt: str | None, ab: float) -> str | None:
                if not txt:
                    return None
                def repl(m, sym):
                    eq = float(m.group(1))
                    phys = max_d_per_fraction(n_fx, eq, ab) * n_fx
                    return f"{sym} {phys:.2f} Gy"
                out = re.sub(r"<\s*([\d.]+)\s*Gy", lambda m: repl(m, "<"), txt)
                out = re.sub(r"≤\s*([\d.]+)\s*Gy", lambda m: repl(m, "≤"), out)
                out = re.sub(r"≥\s*([\d.]+)\s*Gy", lambda m: repl(m, "≥"), out)
                out = re.sub(r"\bV\s*([\d.]+)\s*Gy",
                             lambda m: repl(m, "V"), out)
                out = re.sub(r"0\.03 cc ([\d.]+) Gy",
                             lambda m: f"0.03 cc {max_d_per_fraction(n_fx, float(m.group(1)), ab)*n_fx:.2f} Gy", out)
                out = re.sub(r"(Max(?: [^0-9<≥]+)*)\s*([\d.]+)\s*Gy",
                             lambda m: f"{m.group(1).strip()} {max_d_per_fraction(n_fx, float(m.group(2)), ab)*n_fx:.2f} Gy", out)
                out = re.sub(r"([\d.]+) Gy",
                             lambda m: f"{cap_val:.2f} Gy or 105 % Rx"
                             if float(m.group(1)) > cap_val else m.group(0),
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

            df3_display = pd.DataFrame(agg.values()).reset_index(drop=True)
            st.subheader("3D‑CRT constraints")

            # ✏️ NEW — coverage blurb
            td_blurb = (
                "≥ 95 % of the PTV receives ≥ 95 % of the prescribed dose\n"
                "At least 90 % of the prescribed dose to 100 % of the PTV\n"
                "PTV Dmax ≤ 110 %"
            )
            st.markdown(td_blurb)

            st.dataframe(df3_display, use_container_width=True)

            # 3 – prepend the blurb to the clipboard text
            clip_text = td_blurb + "\n\n" + "\n".join(
                f"{row.OAR}: {row['Plan Specific Constraints']}"
                for _, row in df3_display.iterrows()
            )

            # 4 – copy‑to‑clipboard button (unchanged except variable name)
            components.html(
                f"""
                <button style='margin-top:10px'
                        onclick="navigator.clipboard.writeText(`{clip_text}`)">
                    Copy to clipboard
                </button>
                """,
                height=40
            )

    # ------------------ SBRT branch --------------------------------------
    else:
        sites = st.multiselect("Body site(s)", SBRT_CONSTRAINTS.keys())
        fx = st.selectbox("Fractionation", [3, 5])

        coverage_choice = st.radio(
            "Target‑coverage style",
            ["Standard target coverage", "Accept reduced target coverage"],
            horizontal=True
        )
        
        if sites:
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

            df_sbrt = pd.DataFrame(agg.values()).reset_index(drop=True)
            st.subheader(f"Combined {fx}-fraction SBRT constraints")
            st.dataframe(df_sbrt, use_container_width=True)

            # ── Build copy text, skipping NaNs ──────────────────────────────
            lines = []
            for r in df_sbrt.itertuples():
                parts = [r.OAR]
                if r.Metric:
                    parts.append(f"({r.Metric})")
                if pd.notna(r.Optimal):
                    parts.append(f"Optimal: {r.Optimal}")
                if pd.notna(r.Mandatory):
                    parts.append(f"Mandatory: {r.Mandatory}")
                if r.Endpoint:
                    parts.append(f"Endpoint: {r.Endpoint}")
                lines.append(" — ".join(parts))

            # ── Target‑coverage blurbs ─────────────────────────────────────
            coverage_blurbs = {
                "Standard target coverage": (
                    "SBRT Prescriptions — Standard target coverage\n"
                    "• 95 % of the PTV receives 100 % of the prescription dose\n"
                    "• Minimum PTV dose ≥ 90 % Rx\n"
                    "• 100 % of the CTV receives 100 % Rx\n"
                    "• PTV Dmax ≤ 160 % Rx\n"
                    "• Volume receiving ≥ Rx dose is ≤ 20 % larger than the PTV\n"
                    "• D₂ cm ≤ 50 % Rx\n"
                ),
                "Accept reduced target coverage": (
                    "SBRT Prescriptions — Accept reduced target coverage\n"
                    "• 95 % of the PTV receives 95 % of the prescription dose\n"
                    "• Minimum PTV dose ≥ 85 % Rx\n"
                    "• 100 % of the CTV receives 99 % Rx\n"
                    "• PTV Dmax ≤ 160 % Rx\n"
                    "• Volume receiving ≥ Rx dose is ≤ 20 % larger than the PTV\n"
                    "• D₂ cm ≤ 50 % Rx\n"
                )
            }
            chosen_blurb = coverage_blurbs[coverage_choice]

            # show the blurb above the table
            st.markdown(chosen_blurb)

            # prepend blurb to clipboard string
            clip_sbrt = chosen_blurb + "\n" + "\n".join(lines)
            clip_sbrt = clip_sbrt.replace("`", "\\`")  # escape back‑ticks

            # one‑click copy button
            components.html(
                f"""
                <button style='margin-top:10px'
                        onclick="navigator.clipboard.writeText(`{clip_sbrt}`)">
                    Copy to clipboard
                </button>
                """,
                height=40
            )

# ────────────────────────── Tab 3: OAR Dose Constraints Lookup ──────────────────────────
with tab3:
    st.header("OAR Dose Constraints Lookup")

    # — Friendly user instructions —
    st.info(
        "- **Select treatment setting.**\n"
        "- **Pick at least one OAR.**\n"
        "- **Choose a fractionation scheme.**\n\n"
        "The available dose constraints for your selected OAR(s) per CORSAIR Practical Summary or TG101 are listed below."
    )

    # — Rename the five dropdown labels —
    setting_map = {
        "General (Adult)":                       general_constraints,
        "Experimental CORSAIR OARs":             experimental_constraints,
        "Hodgkin’s Lymphoma":                    hodgkin_constraints,
        "Hypofractionated Breast Radiotherapy":  hypo_constraints,
        "Pediatric Radiotherapy":                pediatric_constraints,
    }
    setting = st.selectbox("Select treatment setting:", list(setting_map.keys()))
    constraints = setting_map[setting]

    # — Pick organs in that scenario —
    organs = sorted(constraints.keys())
    selected_organs = st.multiselect(f"Select OAR(s) for **{setting}**:", organs)

    if not selected_organs:
        st.info("Please select one or more organs to see constraints.")
    else:
        # — Determine which fractionation schemes are actually present —
        scheme_label_map = {
            "conventional":               "Conventional",
            "1_fraction":                 "1 Fraction",
            "3_fraction":                 "3 Fractions",
            "5_fraction":                 "5 Fractions",
            "8_fraction":                 "8 Fractions",
            "moderate_hypofractionation": "Moderate hypofractionation",
            "ultra_hypofractionation":    "Ultra‑hypofractionation",
        }
        available_keys = {
            k
            for organ in selected_organs
            for k in constraints[organ].keys()
        } & set(scheme_label_map)
        if not available_keys:
            st.warning("No fractionation data available for those organs.")
        else:
            # — Let user pick only valid schemes —
            ordered_keys = [k for k in scheme_label_map if k in available_keys]
            labels       = [scheme_label_map[k] for k in ordered_keys]
            scheme_label = st.selectbox("Select fractionation scheme:", labels)
            inv_map      = {v: k for k, v in scheme_label_map.items()}
            scheme_key   = inv_map[scheme_label]

            # — Display the constraints —
            st.subheader(f"{setting} — {scheme_label}")
            for organ in selected_organs:
                st.markdown(f"#### {organ.replace('_',' ')}")
                entries = constraints[organ].get(scheme_key, [])
                if entries:
                    for e in entries:
                        line = e["constraint"]
                        if e.get("category"):
                            line += f"  ({e['category']})"
                        if e.get("source"):
                            line += f" — {e['source']}"
                        st.write(f"- {line}")
                else:
                    st.write("_No constraints defined for this scheme._")

            # — Finally, list your REFERENCES dictionary below —
            st.markdown("---")
            st.subheader("References")
            for idx in sorted(references):
                st.write(f"{idx}. {references[idx]}")
