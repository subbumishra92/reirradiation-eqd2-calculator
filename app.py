import streamlit as st
import math

# ——— Data definitions ———
OARS = [
    "Brain Stem", "Optic Nerve", "Optic Chiasm", "Cochlea",
    "Small Bowel", "Spinal Cord", "Cauda Equina", "Sacral Plexus"
]

OAR_CONSTRAINTS = {
    "Brain Stem":    [{"type":"max",  "value":54}],
    "Optic Nerve":   [{"type":"max",  "value":54}],
    "Optic Chiasm":  [{"type":"max",  "value":54}],
    "Cochlea":       [{"type":"max",  "value":45}],
    "Small Bowel":   [{"type":"max",  "value":52}],
    "Spinal Cord":   [{"type":"max",  "value":45}],
    "Cauda Equina":  [{"type":"max",  "value":45}],
    "Sacral Plexus": [{"type":"max",  "value":45}],
}

OAR_ALPHA_BETA = {
    o: (2 if any(x in o for x in ["Spinal Cord","Chiasm","Brain Stem","Cochlea"]) else 3)
    for o in OARS
}

RECOVERY_FACTORS = {
    "<6 months":   0.00,
    "6–12 months": 0.25,
    "12+ months":  0.50,
}

# ——— Radiobiology utils ———
def bed(n, d, αβ):
    return n * d * (1 + d/αβ)

def eqd2(n, d, αβ):
    return bed(n, d, αβ) / (1 + 2/αβ)

# ——— Fraction‑scheme solver ———
FRACTION_OPTIONS = [1, 3, 5, 10]

def max_d_per_fraction(n, target_eqd2, alpha_beta):
    target_bed = target_eqd2 * (1 + 2/alpha_beta)
    a = n / alpha_beta
    b = n
    c = -target_bed
    disc = b*b - 4*a*c
    if disc < 0:
        return 0.0
    d1 = (-b + math.sqrt(disc)) / (2*a)
    d2 = (-b - math.sqrt(disc)) / (2*a)
    return max(d1, d2)

# ——— Streamlit UI ———
def main():
    st.set_page_config(page_title="Re‑irradiation EQD₂", layout="wide")
    st.title("Re‑irradiation EQD₂ Calculator")

    # Sidebar inputs
    st.sidebar.header("Inputs")
    selected = st.sidebar.multiselect("OAR(s) to re‑irradiate", options=OARS)
    interval = st.sidebar.selectbox("Time since last RT",
        options=["<6 months","6–12 months","12+ months"])

    # Collect up to 3 prior courses per OAR
    prior_data = {}
    for o in selected:
        st.sidebar.subheader(o)
        ctype = OAR_CONSTRAINTS[o][0]["type"]
        n_courses = st.sidebar.selectbox(
            f"Number of prior courses for {o}",
            options=[1,2,3], key=f"nc_{o}"
        )
        courses = []
        for i in range(1, n_courses+1):
            dose = st.sidebar.number_input(
                f"  Course {i} {ctype} dose (Gy)",
                min_value=0.0, step=0.1,
                key=f"dose_{o}_{i}"
            )
            fx = st.sidebar.number_input(
                f"  Course {i} fractions",
                min_value=0, step=1,
                key=f"fx_{o}_{i}"
            )
            # assume unfilled (zero) entries => zero dose
            if dose <= 0 or fx <= 0:
                courses.append({"dose": 0.0, "fractions": 0})
            else:
                courses.append({"dose": dose, "fractions": int(fx)})
        prior_data[o] = {"type": ctype, "courses": courses}

    calculate = st.sidebar.button("Calculate re‑irradiation room")

    # Main results
    if calculate:
        if not selected:
            st.warning("Select at least one OAR before calculating.")
            return

        # 1) compute total prior EQD2 per OAR (sum over courses)
        received = {}
        for o, info in prior_data.items():
            total_eqd2 = 0.0
            αβ = OAR_ALPHA_BETA[o]
            for cr in info["courses"]:
                n, tot = cr["fractions"], cr["dose"]
                if n > 0 and tot > 0:
                    d = tot / n
                    total_eqd2 += eqd2(n, d, αβ)
            received[o] = total_eqd2

        # 2) prepare report
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
                "remaining":       rem
            }

        # 3) display
        st.header("Results")
        for o, stt in report.items():
            with st.expander(o, expanded=True):
                # Detailed breakdown
                st.write(f"- Hard EQD₂ {stt['ctype']} limit: **{stt['limit']:.1f} Gy**")
                st.write(f"- Sum prior EQD₂ received: **{stt['received']:.1f} Gy**")
                st.write(f"- Recovery factor: **{int(stt['recovery_factor']*100)}%**")
                st.write(f"- Amount recovered: **{stt['recovered']:.1f} Gy**")
                st.write(f"- Effective prior EQD₂: **{stt['effective']:.1f} Gy**")
                st.write(f"- Remaining re‑irradiation room: **{stt['remaining']:.1f} Gy**")

                # New max constraint first
                new_limit = stt["remaining"]
                st.success(f"→ New EQD₂ {stt['ctype']} max constraint: {new_limit:.1f} Gy")

                # Markdown list of permissible regimens with italics
                αβ = OAR_ALPHA_BETA[o]
                md_lines = ["**Permissible regimens:**"]
                for n in FRACTION_OPTIONS:
                    d = max_d_per_fraction(n, new_limit, αβ)
                    total = d * n
                    md_lines.append(f"- {n} fx: {total:.1f} Gy (*{d:.2f} Gy/fx*)")
                st.markdown("\n".join(md_lines))

if __name__=="__main__":
    main()
