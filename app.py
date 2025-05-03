import streamlit as st
import math

# ——— Page config ———
st.set_page_config(page_title="Re‑irradiation EQD₂", layout="wide")

# ——— Data & defaults ———
OARS = ["Brain Stem","Optic Nerve","Optic Chiasm","Cochlea",
        "Small Bowel","Spinal Cord","Cauda Equina","Sacral Plexus"]
OAR_CONSTRAINTS = {o:[{"type":"max","value":v}] 
    for o,v in {"Brain Stem":54,"Optic Nerve":54,"Optic Chiasm":54,
                "Cochlea":45,"Small Bowel":52,"Spinal Cord":45,
                "Cauda Equina":45,"Sacral Plexus":45}.items()}
OAR_ALPHA_BETA = {o:(2 if o in ["Spinal Cord","Optic Chiasm","Brain Stem",
                                "Optic Nerve","Sacral Plexus","Cauda Equina"] else 3)
                  for o in OARS}
RECOVERY = {"<6 months":0.0,"6–12 months":0.25,"12+ months":0.50}
FRACTIONS = [1,3,5,10]

# ——— Radiobiology ———
def bed(n,d,αβ): return n*d*(1 + d/αβ)
def eqd2(n,d,αβ): return bed(n,d,αβ)/(1+2/αβ)
def max_dpf(n, eqd2_lim, αβ):
    tb = eqd2_lim*(1+2/αβ)
    a,b,c = n/αβ, n, -tb
    disc = b*b - 4*a*c
    if disc<0: return 0.0
    d1 = (-b+math.sqrt(disc))/(2*a)
    d2 = (-b-math.sqrt(disc))/(2*a)
    return max(d1,d2)

# ——— Session state ———
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "custom_ab" not in st.session_state:
    st.session_state.custom_ab = {}

st.title("Re‑irradiation EQD₂ Calculator")

# ─── INPUT STAGE ─────────────────────────────────────────────────────────────
if st.session_state.stage == "input":
    selected = st.multiselect("Select OAR(s)", OARS)
    interval = st.selectbox("Time since last RT", list(RECOVERY.keys()))

    prior_data = {}
    for o in selected:
        st.markdown(f"**{o}**")
        ctype = OAR_CONSTRAINTS[o][0]["type"]
        n_courses = st.selectbox(f"How many prior courses for {o}?", [1,2,3], key=o+"_nc")
        courses = []
        for i in range(1, n_courses+1):
            dose = st.number_input(f" Course {i} {ctype} dose (Gy)", min_value=0.0, step=0.1, key=f"{o}_d{i}")
            fx   = st.number_input(f" Course {i} fractions",     min_value=0,   step=1,   key=f"{o}_f{i}")
            if dose>0 and fx>0:
                courses.append((dose,fx))
        prior_data[o] = courses

    if st.button("Calculate"):
        # Save inputs
        st.session_state.selected   = selected
        st.session_state.interval   = interval
        st.session_state.prior_data = prior_data
        st.session_state.stage      = "results"
        st.experimental_rerun()

# ─── RESULTS STAGE ────────────────────────────────────────────────────────────
elif st.session_state.stage == "results":
    selected   = st.session_state.selected
    interval   = st.session_state.interval
    prior_data = st.session_state.prior_data

    # Compute delivered EQD2
    report = {}
    for o, courses in prior_data.items():
        total = 0.0
        ab    = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
        for dose,fx in courses:
            total += eqd2(fx, dose/fx, ab)
        report[o] = {"delivered": total, "ab": ab}

    # Apply recovery and compute remaining
    for o, entry in report.items():
        lim   = OAR_CONSTRAINTS[o][0]["value"]
        recov = entry["delivered"] * RECOVERY[interval]
        eff   = entry["delivered"] - recov
        rem   = max(lim - eff, 0.0)
        report[o].update({
            "limit":lim, "recovered":recov,
            "effective":eff, "remaining":rem
        })

    st.header("Results")
    for o, stt in report.items():
        with st.expander(o, expanded=True):
            st.write(f"- Hard EQD₂ max: **{stt['limit']:.1f} Gy**")
            st.write(f"- Delivered EQD₂: **{stt['delivered']:.1f} Gy**")
            st.write(f"- Recovered: **{stt['recovered']:.1f} Gy**")
            st.write(f"- Effective: **{stt['effective']:.1f} Gy**")
            st.write(f"- Remaining: **{stt['remaining']:.1f} Gy**")
            st.info(f"α/β used: **{stt['ab']} Gy**")
            st.success(f"→ New EQD₂ max: {stt['remaining']:.1f} Gy")
            lines = ["**Permissible regimens:**"]
            for n in FRACTIONS:
                d = max_dpf(n, stt["remaining"], stt["ab"])
                lines.append(f"- {n} fx: {d*n:.1f} Gy (*{d:.2f} Gy/fx*)")
            st.markdown("\n".join(lines))

    # Action buttons
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back to inputs"):
            st.session_state.stage = "input"
            st.experimental_rerun()
    with c2:
        if st.button("Edit α/β"):
            st.session_state.stage = "edit_ab"
            st.experimental_rerun()

# ─── EDIT α/β STAGE ───────────────────────────────────────────────────────────
elif st.session_state.stage == "edit_ab":
    st.header("Override α/β ratios")
    new_ab = {}
    for o in st.session_state.selected:
        current = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
        val = st.number_input(f"{o} α/β (Gy)", value=float(current), step=0.1, min_value=0.1, key="ab_"+o)
        new_ab[o] = val

    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Cancel"):
            st.session_state.stage = "results"
            st.experimental_rerun()
    with c2:
        if st.button("Apply and Recalculate"):
            st.session_state.custom_ab.update(new_ab)
            st.session_state.stage = "results"
            st.experimental_rerun()
