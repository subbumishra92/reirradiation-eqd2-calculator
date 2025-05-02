import streamlit as st

# ——— Data definitions ———
OARS = [
    "Bile Duct", "Bone (Weight‑bearing)", "Brain Stem", "Cervical Esophagus",
    "Chiasm / Optic Nerve", "Cochlea", "Colon", "Duodenum", "Esophagus",
    "Femoral Heads", "Glottic Larynx", "Heart", "Hippocampi", "Kidneys",
    "Lens", "Liver", "Lung", "Mandible", "Oral Cavity", "Ovaries", "Parotid",
    "Penile Bulb", "Pharyngeal Constrictors", "Pituitary", "Small Bowel",
    "Spleen", "Spinal Cord", "Stomach", "Submandibular Gland", "Testicles",
    "Thyroid"
]

OAR_CONSTRAINTS = {
    "Bile Duct":            [{"type":"max",  "value":63}],
    "Bone (Weight‑bearing)":[{"type":"mean","value":37}],
    "Brain Stem":           [{"type":"max",  "value":54}],
    "Cervical Esophagus":   [{"type":"mean","value":30}],
    "Chiasm / Optic Nerve": [{"type":"max",  "value":54}],
    "Cochlea":              [{"type":"mean","value":35}],
    "Colon":                [{"type":"max",  "value":60}],
    "Duodenum":             [{"type":"max",  "value":55}],
    "Esophagus":            [{"type":"mean","value":34}],
    "Femoral Heads":        [{"type":"mean","value":50}],
    "Glottic Larynx":       [{"type":"mean","value":45}],
    "Heart":                [{"type":"mean","value":20}],
    "Hippocampi":           [{"type":"max",  "value":16}],
    "Kidneys": [
        {"type":"mean","value":15},
        {"type":"mean","value":9,  "note":"single functional kidney, V18<15%"}
    ],
    "Lens":                 [{"type":"max",  "value":7}],
    "Liver":                [{"type":"mean","value":25}],
    "Lung":                 [{"type":"mean","value":20}],
    "Mandible":             [{"type":"max",  "value":70}],
    "Oral Cavity":          [{"type":"mean","value":30}],
    "Ovaries":              [{"type":"max",  "value":3}],
    "Parotid":              [{"type":"mean","value":26}],
    "Penile Bulb":          [{"type":"mean","value":52}],
    "Pharyngeal Constrictors":[{"type":"mean","value":50}],
    "Pituitary":            [{"type":"mean","value":40}],
    "Small Bowel":          [{"type":"max",  "value":52}],
    "Spleen":               [{"type":"mean","value":9}],
    "Spinal Cord":          [{"type":"max",  "value":45}],
    "Stomach":              [{"type":"max",  "value":50}],
    "Submandibular Gland":  [{"type":"mean","value":39}],
    "Testicles":            [{"type":"max",  "value":3}],
    "Thyroid":              [{"type":"mean","value":37}],
}

OAR_ALPHA_BETA = {
    o: (2 if any(x in o for x in ["Spinal Cord","Chiasm","Brain Stem","Lens","Mandible","Hippocampi","Cochlea","Ovaries","Parotid","Submandibular Gland","Testicles"])
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
    return bed(n, d, αβ)/(1 + 2/αβ)


# ——— Streamlit UI ———
def main():
    st.title("Re‑irradiation EQD₂ Calculator")

    # 1) OAR selection
    selected = st.multiselect(
        "Which OAR(s) are being re‑irradiated?",
        options=OARS
    )
    if not selected:
        st.info("Select at least one OAR to continue.")
        return

    # 2) Prior dose & fractions
    prior_data = {}
    for o in selected:
        ctype = OAR_CONSTRAINTS[o][0]["type"]
        st.subheader(o)
        dose = st.number_input(f"  Prior {ctype} dose (Gy)", min_value=0.0, step=0.1, key=f"dose_{o}")
        fx   = st.number_input(f"  Number of fractions", min_value=1, step=1, key=f"fx_{o}")
        prior_data[o] = {"type": ctype, "dose": dose, "fractions": int(fx)}

    # 3) Time since last RT
    interval = st.selectbox(
        "Time since last RT",
        options=["<6 months","6–12 months","12+ months"]
    )

    # 4) Calculate button
    if st.button("Calculate re‑irradiation room"):
        # compute prior EQD2
        received = {
            o: eqd2(info["fractions"], info["dose"]/info["fractions"], OAR_ALPHA_BETA[o])
            for o,info in prior_data.items()
        }
        # compute room
        report = {}
        for o, rec in received.items():
            lim = OAR_CONSTRAINTS[o][0]["value"]
            f   = RECOVERY_FACTORS[interval]
            recov = rec * f
            eff   = rec - recov
            rem   = max(lim - eff, 0.0)
            report[o] = {
                "ctype": OAR_CONSTRAINTS[o][0]["type"],
                "limit": lim, "received": rec,
                "recovery_factor": f, "recovered": recov,
                "effective": eff, "remaining": rem
            }

        # 5) Display results
        st.markdown("### Results")
        for o,stt in report.items():
            with st.expander(o):
                st.write(f"Hard EQD₂ {stt['ctype']}: {stt['limit']:.1f} Gy")
                st.write(f"Prior EQD₂ received: {stt['received']:.1f} Gy")
                st.write(f"Recovery factor: {int(stt['recovery_factor']*100)}%")
                st.write(f"Amount recovered: {stt['recovered']:.1f} Gy")
                st.write(f"Effective prior EQD₂: {stt['effective']:.1f} Gy")
                st.write(f"Remaining room: {stt['remaining']:.1f} Gy")
                st.success(f"→ New EQD₂ {stt['ctype']} constraint: {stt['remaining']:.1f} Gy")

if __name__=="__main__":
    main()
