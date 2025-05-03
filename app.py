import streamlit as st
import math

# ——— Page config ———
st.set_page_config(page_title="Re‑irradiation EQD₂", layout="wide")

# ——— Data definitions ———
OARS = [
    "Brain Stem", "Optic Nerve", "Optic Chiasm", "Cochlea",
    "Small Bowel", "Spinal Cord", "Cauda Equina", "Sacral Plexus"
]

OAR_CONSTRAINTS = {
    o: [{"type":"max","value":v}]
    for o,v in {
        "Brain Stem":54, "Optic Nerve":54, "Optic Chiasm":54,
        "Cochlea":45, "Small Bowel":52, "Spinal Cord":45,
        "Cauda Equina":45, "Sacral Plexus":45
    }.items()
}

# Exact default α/β map
OAR_ALPHA_BETA = {
    o: (2 if o in [
            "Spinal Cord","Optic Chiasm","Brain Stem",
            "Optic Nerve","Sacral Plexus","Cauda Equina"
        ] else 3)
    for o in OARS
}

RECOVERY_FACTORS = {"<6 months":0.0,"6–12 months":0.25,"12+ months":0.50}
FRACTION_OPTIONS   = [1,3,5,10]

# ——— Radiobiology & solver ———
def bed(n, d, αβ): return n * d * (1 + d/αβ)
def eqd2(n, d, αβ): return bed(n, d, αβ) / (1 + 2/αβ)

def max_d_per_fraction(n, target_eqd2, αβ):
    target_bed = target_eqd2 * (1 + 2/αβ)
    a, b, c = n/αβ, n, -target_bed
    disc = b*b - 4*a*c
    if disc < 0: return 0.0
    d1 = (-b + math.sqrt(disc)) / (2*a)
    d2 = (-b - math.sqrt(disc)) / (2*a)
    return max(d1, d2)

# ——— Session state flags ———
if "calculated" not in st.session_state:
    st.session_state.calculated = False
if "edit_ab" not in st.session_state:
    st.session_state.edit_ab = False
if "custom_ab" not in st.session_state:
    st.session_state.custom_ab = {}

# ——— UI ———
st.title("Re‑irradiation EQD₂ Calculator")

# Center inputs in three columns
left, center, right = st.columns([1,2,1])
with center:
    st.header("Inputs")

    selected = st.multiselect("OAR(s) to re‑irradiate", OARS)
    interval = st.selectbox("Time since last RT",
        ["<6 months","6–12 months","12+ months"])

    prior_data = {}
    for o in selected:
        st.subheader(o)
        ctype = OAR_CONSTRAINTS[o][0]["type"]
        n_courses = st.selectbox(
            f"Number of prior courses for {o}", [1,2,3], key=f"nc_{o}"
        )
        courses = []
        for i in range(1, n_courses+1):
            dose = st.number_input(
                f"  Course {i} {ctype} dose (Gy)",
                min_value=0.0, step=0.1, key=f"dose_{o}_{i}"
            )
            fx = st.number_input(
                f"  Course {i} fractions",
                min_value=0, step=1, key=f"fx_{o}_{i}"
            )
            if dose > 0 and fx > 0:
                courses.append({"dose": dose, "fractions": int(fx)})
        prior_data[o] = {"courses": courses}

    calc = st.button("Calculate re‑irradiation room")

# ——— Compute & display results ———
if calc:
    if not selected:
        st.warning("Please select at least one OAR.")
    else:
        # 1) Sum prior EQD2 with default or custom α/β
        received = {}
        for o, info in prior_data.items():
            total_eqd2 = 0.0
            αβ = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
            for cr in info["courses"]:
                n, tot = cr["fractions"], cr["dose"]
                d = tot / n
                total_eqd2 += eqd2(n, d, αβ)
            received[o] = total_eqd2

        # 2) Build report
        report = {}
        for o, rec in received.items():
            lim   = OAR_CONSTRAINTS[o][0]["value"]
            f     = RECOVERY_FACTORS[interval]
            recov = rec * f
            eff   = rec - recov
            rem   = max(lim - eff, 0.0)
            report[o] = {
                "ctype":           OAR_CONSTRAINTS[o][0]["type"],
                "limit":           lim,
                "received":        rec,
                "recovery_factor": f,
                "recovered":       recov,
                "effective":       eff,
                "remaining":       rem,
                "alpha_beta":      st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
            }

        # render results
        st.header("Results")
        for o, stt in report.items():
            with st.expander(o, expanded=True):
                st.write(f"- Hard EQD₂ {stt['ctype']} limit: **{stt['limit']:.1f} Gy**")
                st.write(f"- Sum prior EQD₂ received: **{stt['received']:.1f} Gy**")
                st.write(f"- Recovery factor: **{int(stt['recovery_factor']*100)}%**")
                st.write(f"- Amount recovered: **{stt['recovered']:.1f} Gy**")
                st.write(f"- Effective prior EQD₂: **{stt['effective']:.1f} Gy**")
                st.write(f"- Remaining room: **{stt['remaining']:.1f} Gy**")

                # α/β used
                st.info(f"α/β used for {o}: **{stt['alpha_beta']} Gy**")

                # new constraint
                new_lim = stt["remaining"]
                st.success(f"→ New EQD₂ {stt['ctype']} max constraint: {new_lim:.1f} Gy")

                # permissible regimens
                md = ["**Permissible regimens:**"]
                for n in FRACTION_OPTIONS:
                    d = max_d_per_fraction(n, new_lim, stt["alpha_beta"])
                    total = d * n
                    md.append(f"- {n} fx: {total:.1f} Gy (*{d:.2f} Gy/fx*)")
                st.markdown("\n".join(md))

        # 3) Actions: Edit inputs or Edit α/β
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            if st.button("Edit inputs"):
                st.session_state.calculated = False
                st.session_state.edit_ab = False
                st.experimental_rerun()
            if st.button("Edit α/β"):
                st.session_state.edit_ab = True
                st.experimental_rerun()

        # 4) α/β override form
        if st.session_state.edit_ab:
            st.header("Override α/β ratios")
            new_ab = {}
            for o in selected:
                default_ab = st.session_state.custom_ab.get(o, OAR_ALPHA_BETA[o])
                val = st.number_input(
                    f"{o} α/β (Gy)",
                    min_value=0.1, step=0.1,
                    value=float(default_ab),
                    key=f"ab_{o}"
                )
                new_ab[o] = val

            if st.button("Apply new α/β and Recalculate"):
                st.session_state.custom_ab.update(new_ab)
                st.session_state.edit_ab = False
                st.experimental_rerun()
