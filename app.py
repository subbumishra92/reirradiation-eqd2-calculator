import streamlit as st
import math

# ——— Page config ———
st.set_page_config(page_title="Re‑irradiation EQD₂", layout="wide")

# ——— Data & defaults ———
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

RECOVERY_FACTORS = {
    "<6 months": 0.00,
    "6–12 months": 0.25,
    "12+ months": 0.50
}

FRACTION_OPTIONS = [1, 3, 5, 10]

# ——— Radiobiology & solver ———
def bed(n, d, αβ): return n * d * (1 + d/αβ)
def eqd2(n, d, αβ): return bed(n, d, αβ) / (1 + 2/αβ)
def max_d_per_fraction(n, target_eqd2, αβ):
    tb = target_eqd2 * (1 + 2/αβ)
    a, b, c = n/αβ, n, -tb
    disc = b*b - 4*a*c
    if disc<0: return 0.0
    d1 = (-b + math.sqrt(disc))/(2*a)
    d2 = (-b - math.sqrt(disc))/(2*a)
    return max(d1, d2)

# ——— Session state flags ———
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "custom_ab" not in st.session_state:
    st.session_state.custom_ab = {}

st.title("Re‑irradiation EQD₂ Calculator")

# ─── INPUT STAGE ─────────────────────────────────────────────────────────────
if st.session_state.stage == "input":
    selected = st.multiselect("Select OAR(s)", OARS)
    global_interval = st.selectbox("Time since last RT to new course", list(RECOVERY_FACTORS.keys()))

    prior_data = {}
    for o in selected:
        st.markdown(f"### {o}")
        ctype = OAR_CONSTRAINTS[o][0]["type"]
        n_courses = st.selectbox(f"How many prior courses for {o}?", [1,2,3], key=f"{o}_nc")
        courses = []
        for i in range(1, n_courses+1):
            if i > 1:
                interval_prev = st.selectbox(f"Interval between course {i-1} and {i}", list(RECOVERY_FACTORS.keys()), key=f"{o}_int_{i}")
            else:
                interval_prev = None
            dose = st.number_input(f"Course {i} {ctype} dose (Gy)", min_value=0.0, step=0.1, key=f"{o}_d{i}")
            fx   = st.number_input(f"Course {i} fractions",     min_value=0,   step=1,   key=f"{o}_f{i}")
            if dose>0 and fx>0:
                courses.append({
                    "dose": dose,
                    "fractions": int(fx),
                    "interval_prev": interval_prev
                })
        prior_data[o] = courses

    if st.button("Calculate"):
        st.session_state.selected = selected
        st.session_state.global_interval = global_interval
        st.session_state.prior_data = prior_data
        st.session_state.stage = "results"
        st.rerun()

# ─── RESULTS STAGE ────────────────────────────────────────────────────────────
elif st.session_state.stage == "results":
    selected       = st.session_state.selected
    global_interval= st.session_state.global_interval
    prior_data     = st.session_state.prior_data

    report = {}
    for o, courses in prior_data.items():
        ab = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
        # iterative cumulative with inter-course recovery
        cumulative = 0.0
        raw_sum    = 0.0
        for idx, cr in enumerate(courses):
            eq = eqd2(cr["fractions"], cr["dose"]/cr["fractions"], ab)
            raw_sum += eq
            if idx == 0:
                cumulative = eq
            else:
                f = RECOVERY_FACTORS[cr["interval_prev"]]
                cumulative = cumulative*(1-f) + eq
        # recovery after last course to new RT
        f_last = RECOVERY_FACTORS[global_interval]
        effective = cumulative*(1 - f_last)
        total_recovered = raw_sum - effective
        limit = OAR_CONSTRAINTS[o][0]["value"]
        remaining = max(limit - effective, 0.0)

        report[o] = {
            "raw_sum": raw_sum,
            "recovered": total_recovered,
            "effective": effective,
            "limit": limit,
            "remaining": remaining,
            "ab": ab
        }

    st.header("Results")
    for o, stt in report.items():
        with st.expander(o, expanded=True):
            st.write(f"- Hard EQD₂ max: **{stt['limit']:.1f} Gy**")
            st.write(f"- Sum raw EQD₂ delivered: **{stt['raw_sum']:.1f} Gy**")
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

# ─── EDIT α/β STAGE ───────────────────────────────────────────────────────────
elif st.session_state.stage == "edit_ab":
    st.header("Override α/β ratios")
    new_ab = {}
    for o in st.session_state.selected:
        default = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
        val = st.number_input(
            f"{o} α/β (Gy)",
            min_value=0.1, step=0.1,
            value=float(default),
            key=f"ab_{o}"
        )
        new_ab[o] = val

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Cancel"):
            st.session_state.stage = "results"
            st.rerun()
    with c2:
        if st.button("Apply and Recalculate"):
            st.session_state.custom_ab.update(new_ab)
            st.session_state.stage = "results"
            st.rerun()
