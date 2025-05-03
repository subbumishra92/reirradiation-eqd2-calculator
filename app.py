import streamlit as st
import math

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

OAR_ALPHA_BETA = { o: (2 if "Spinal Cord" in o or "Chiasm" in o or "Brain Stem" in o or "Cochlea" in o else 3) for o in OARS }
RECOVERY_FACTORS = {"<6 months":0.0,"6–12 months":0.25,"12+ months":0.50}
FRACTION_OPTIONS = [1,3,5,10]

# ——— Radiobiology & solver ———
def bed(n,d,αβ): return n*d*(1+d/αβ)
def eqd2(n,d,αβ): return bed(n,d,αβ)/(1+2/αβ)
def max_d_per_fraction(n,target_eqd2,αβ):
    tb = target_eqd2*(1+2/αβ)
    a,b,c = n/αβ, n, -tb
    disc = b*b - 4*a*c
    if disc<0: return 0.0
    d1 = (-b + math.sqrt(disc)) / (2*a)
    d2 = (-b - math.sqrt(disc)) / (2*a)
    return max(d1,d2)

# ——— Streamlit UI ———
def main():
    st.set_page_config(page_title="Re‑irradiation EQD₂", layout="wide")
    st.title("Re‑irradiation EQD₂ Calculator")

    # init session flag
    if "calculated" not in st.session_state:
        st.session_state.calculated = False

    # Inputs form
    with st.form("input_form"):
        st.header("Inputs")
        selected = st.multiselect("OAR(s) to re‑irradiate", OARS)
        interval = st.selectbox("Time since last RT",
                                ["<6 months","6–12 months","12+ months"])
        prior_data = {}
        for o in selected:
            st.subheader(o)
            ctype = OAR_CONSTRAINTS[o][0]["type"]
            n_courses = st.selectbox(f"Number of prior courses for {o}", [1,2,3], key=f"nc_{o}")
            courses = []
            for i in range(1, n_courses+1):
                dose = st.number_input(f"  Course {i} {ctype} dose (Gy)", min_value=0.0, step=0.1, key=f"dose_{o}_{i}")
                fx   = st.number_input(f"  Course {i} fractions",     min_value=0,   step=1,   key=f"fx_{o}_{i}")
                if dose>0 and fx>0:
                    courses.append({"dose":dose,"fractions":int(fx)})
            prior_data[o] = {"courses":courses}
        submit = st.form_submit_button("Calculate")

    # When form is submitted, set flag and save inputs
    if submit:
        st.session_state.selected   = selected
        st.session_state.interval   = interval
        st.session_state.prior_data = prior_data
        st.session_state.calculated = True

    # Results
    if st.session_state.calculated:
        selected   = st.session_state.selected
        interval   = st.session_state.interval
        prior_data = st.session_state.prior_data

        # ... do your EQD2/recovery calculations exactly as before ...

        st.header("Results")
        for o, stt in report.items():
            with st.expander(o, expanded=True):
                # ... breakdown + permissible regimens ...

        if st.button("Edit inputs"):
            st.session_state.calculated = False

