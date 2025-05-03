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

RECOVERY_FACTORS = {"<6 months":0.00, "6–12 months":0.25, "12+ months":0.50}
FRACTION_OPTIONS   = [1,3,5,10]

# ——— Radiobiology & solver ———
@st.cache_data
def eqd2(n, d, αβ):
    return n * d * (1 + d/αβ) / (1 + 2/αβ)

@st.cache_data
def max_d_per_fraction(n, target_eqd2, αβ):
    tb = target_eqd2 * (1 + 2/αβ)
    a,b,c = n/αβ, n, -tb
    disc = b*b - 4*a*c
    if disc < 0: return 0.0
    d1 = (-b + math.sqrt(disc)) / (2*a)
    d2 = (-b - math.sqrt(disc)) / (2*a)
    return max(d1, d2)

# ——— Helper: compute report ———
def compute_report(selected, global_interval, prior_data, override_ab):
    report = {}
    for o in selected:
        ab = override_ab.get(o, OAR_ALPHA_BETA[o])
        # accumulate with inter‐course recovery
        cumulative = 0.0
        raw_sum = 0.0
        courses = prior_data[o]
        for idx, cr in enumerate(courses):
            eq = eqd2(cr["fractions"], cr["dose"]/cr["fractions"], ab)
            raw_sum += eq
            if idx==0:
                cumulative = eq
            else:
                f = RECOVERY_FACTORS[cr["interval_prev"]]
                cumulative = cumulative*(1-f) + eq
        # final recovery to upcoming course
        f_last = RECOVERY_FACTORS[global_interval]
        effective = cumulative*(1-f_last)
        recovered = raw_sum - effective
        limit = OAR_CONSTRAINTS[o][0]["value"]
        remaining = max(limit - effective, 0.0)
        report[o] = {
            "limit":     limit,
            "raw_sum":   raw_sum,
            "recovered": recovered,
            "effective": effective,
            "remaining": remaining,
            "ab":        ab
        }
    return report

# ——— Helper: render results ———
def show_oar_results(o, data):
    st.write(f"- Hard EQD₂ max limit: **{data['limit']:.1f} Gy**")
    st.write(f"- Sum raw EQD₂ delivered: **{data['raw_sum']:.1f} Gy**")
    st.write(f"- Total recovered: **{data['recovered']:.1f} Gy**")
    st.write(f"- Effective prior EQD₂: **{data['effective']:.1f} Gy**")
    st.write(f"- Remaining room: **{data['remaining']:.1f} Gy**")
    st.info(f"α/β used: **{data['ab']} Gy**")
    st.success(f"→ New EQD₂ max constraint: {data['remaining']:.1f} Gy")
    lines = ["**Permissible regimens:**"]
    for n in FRACTION_OPTIONS:
        d = max_d_per_fraction(n, data["remaining"], data["ab"])
        lines.append(f"- {n} fx: {d*n:.1f} Gy (*{d:.2f} Gy/fx*)")
    st.markdown("\n".join(lines))

# ——— Main form ———
with st.form("calc_form", clear_on_submit=False):
    st.header("Re‑irradiation EQD₂ Inputs")

    selected = st.multiselect("Which OAR(s) to re‑irradiate?", OARS)
    if selected:
        global_interval = st.selectbox(
            "Time since last RT to upcoming course",
            list(RECOVERY_FACTORS.keys())
        )

        # Collect up to 3 prior courses
        prior_data = {}
        for o in selected:
            st.subheader(o)
            ctype = OAR_CONSTRAINTS[o][0]["type"]
            n_courses = st.selectbox(
                f"Number of prior courses for {o}", [1,2,3], key=f"{o}_nc"
            )
            courses = []
            for i in range(1, 4):
                if i <= n_courses:
                    if i > 1:
                        interval_prev = st.selectbox(
                            f"Interval between course {i-1} & {i}",
                            list(RECOVERY_FACTORS.keys()),
                            key=f"{o}_int_{i}"
                        )
                    else:
                        interval_prev = None

                    dose = st.number_input(
                        f"Course {i} {ctype} dose (Gy)",
                        min_value=0.0, step=0.1, key=f"{o}_dose_{i}"
                    )
                    fx = st.number_input(
                        f"Course {i} fractions",
                        min_value=0, step=1, key=f"{o}_fx_{i}"
                    )
                    if dose > 0 and fx > 0:
                        courses.append({
                            "dose": dose,
                            "fractions": int(fx),
                            "interval_prev": interval_prev
                        })
                else:
                    # ensure consistent form state
                    st.empty()
            prior_data[o] = courses

        # Optional α/β override
        override_ab = {}
        st.subheader("Optional: override α/β values")
        for o in selected:
            default_ab = OAR_ALPHA_BETA[o]
            override_ab[o] = st.number_input(
                f"{o} α/β (Gy)",
                min_value=0.1, step=0.1,
                value=float(default_ab),
                key=f"{o}_ab"
            )

    submitted = st.form_submit_button("Calculate")

if submitted and selected:
    report = compute_report(selected, global_interval, prior_data, override_ab)
    st.header("Results")
    for organ, metrics in report.items():
        with st.expander(organ, expanded=True):
            show_oar_results(organ, metrics)
