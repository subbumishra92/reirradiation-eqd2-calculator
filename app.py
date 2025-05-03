def main():
    st.set_page_config(page_title="Re‑irradiation EQD₂", layout="wide")
    st.title("Re‑irradiation EQD₂ Calculator")

    # Initialize session flag
    if "calculated" not in st.session_state:
        st.session_state.calculated = False

    # --- Input form ---
    with st.form("input_form"):
        st.header("Inputs")
        selected = st.multiselect("OAR(s) to re‑irradiate", OARS)
        interval = st.selectbox(
            "Time since last RT",
            ["<6 months","6–12 months","12+ months"]
        )

        prior_data = {}
        for o in selected:
            st.subheader(o)
            ctype = OAR_CONSTRAINTS[o][0]["type"]
            n_courses = st.selectbox(
                f"Number of prior courses for {o}", [1, 2, 3], key=f"nc_{o}"
            )
            courses = []
            for i in range(1, n_courses + 1):
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

        submit = st.form_submit_button("Calculate")

    # When form is submitted, save inputs and flip the flag
    if submit:
        st.session_state.selected   = selected
        st.session_state.interval   = interval
        st.session_state.prior_data = prior_data
        st.session_state.calculated = True

    # --- Results block ---
    if st.session_state.calculated:
        selected   = st.session_state.selected
        interval   = st.session_state.interval
        prior_data = st.session_state.prior_data

        # Compute EQD2 and recovery (as before)...
        received = {}
        for o, info in prior_data.items():
            total_eqd2 = 0.0
            αβ = OAR_ALPHA_BETA[o]
            for cr in info["courses"]:
                n, tot = cr["fractions"], cr["dose"]
                d = tot / n
                total_eqd2 += eqd2(n, d, αβ)
            received[o] = total_eqd2

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

        st.header("Results")
        for o, stt in report.items():
            with st.expander(o, expanded=True):
                st.write(f"- Hard EQD₂ {stt['ctype']} limit: **{stt['limit']:.1f} Gy**")
                st.write(f"- Sum prior EQD₂ received: **{stt['received']:.1f} Gy**")
                st.write(f"- Recovery factor: **{int(stt['recovery_factor']*100)}%**")
                st.write(f"- Amount recovered: **{stt['recovered']:.1f} Gy**")
                st.write(f"- Effective prior EQD₂: **{stt['effective']:.1f} Gy**")
                st.write(f"- Remaining re‑irradiation room: **{stt['remaining']:.1f} Gy**")

                new_lim = stt["remaining"]
                st.success(f"→ New EQD₂ {stt['ctype']} max constraint: {new_lim:.1f} Gy")

                αβ = OAR_ALPHA_BETA[o]
                md_lines = ["**Permissible regimens:**"]
                for n in FRACTION_OPTIONS:
                    d = max_d_per_fraction(n, new_lim, αβ)
                    total = d * n
                    md_lines.append(f"- {n} fx: {total:.1f} Gy (*{d:.2f} Gy/fx*)")
                st.markdown("\n".join(md_lines))

        # Edit button below results
        if st.button("Edit inputs"):
            st.session_state.calculated = False

if __name__ == "__main__":
    main()
