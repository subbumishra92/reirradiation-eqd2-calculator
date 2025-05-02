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
    o: (2 if any(x in o for x in ["Spinal Cord","Chiasm","Brain Stem","Cochlea"])
        else 3)
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
    """Solve for d in BED equation given n and target EQD₂."""
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

    # Sidebar form for inputs
    with st.sidebar.form("inputs", clear_on_submit=False):
        st.header("Inputs")

        selected = st.multiselect(
            "OAR(s) to re‑irradiate",
            options=OARS,
            help="Select one or more organs at risk"
        )

        interval = st.selectbox(
            "Time since last RT",
            options=["<6 months","6–12 months","12+ months"],
            help="Tissue recovery fraction applied to prior dose"
        )

        prior_data = {}
        for o in selected:
            st.subheader(o)
            ctype = OAR_CONSTRAINTS[o][0]["type"]
            col1, col2 = st.columns(2)
            with col1:
                dose = st.number_input(
                    f"Prior {ctype} dose (Gy)",
                    min_value=0.0, step=0.1,
                    key=f"dose_{o}"
                )
            with col2:
                fx = st.number_input(
                    "Fractions",
                    min_value=1, step=1,
                    key=f"fx_{o}"
                )
            prior_data[o] = {"type": ctype, "dose": dose, "fractions": int(fx)}

        calculate = st.form_submit_button("Calculate")

    # Only calculate & render results when user clicks
    if calculate and selected:
        # 1) compute prior EQD2
        received = {
            o: eqd2(data["fractions"], data["dose"]/data["fractions"], OAR_ALPHA_BETA[o])
            for o, data in prior_data.items()
        }

        # 2) compute remaining room
        report = {}
        for o, rec in received.items():
            lim = OAR_CONSTRAINTS[o][0]["value"]
            f   = RECOVERY_FACTORS[interval]
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

        # 3) display in main area
        st.header("Results")
        for o, stt in report.items():
            with st.expander(o, expanded=True):
                st.write(f"**Hard EQD₂ {stt['ctype']} limit:** {stt['limit']:.1f} Gy")
                st.write(f"**Prior EQD₂ received:**      {stt['received']:.1f} Gy")
                st.write(f"**Recovery factor:**          {int(stt['recovery_factor']*100)} %")
                st.write(f"**Amount recovered:**         {stt['recovered']:.1f} Gy")
                st.write(f"**Effective prior EQD₂:**     {stt['effective']:.1f} Gy")
                st.write(f"**Remaining room:**           {stt['remaining']:.1f} Gy")

                # ——— New fractionation guidance ———
                st.markdown("**Dose‑per‑fraction limits for remaining EQD₂:**")
                frac_limits = []
                αβ = OAR_ALPHA_BETA[o]
                for n in FRACTION_OPTIONS:
                    d = max_d_per_fraction(n, stt["remaining"], αβ)
                    frac_limits.append((n, f"{d:.2f} Gy"))
                st.table({
                    "Fractions":    [n for n,_ in frac_limits],
                    "Max dose/fx":  [d for _,d in frac_limits]
                })

                st.success(f"→ New EQD₂ {stt['ctype']} constraint: {stt['remaining']:.1f} Gy")

    elif not selected and calculate:
        st.warning("Please select at least one OAR before calculating.")

if __name__=="__main__":
    main()
