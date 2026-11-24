import pandas as pd
import streamlit as st
from PIL import Image

from llm import analyze_report
from range_checker import resolve_statuses

import fitz  


def load_image(file):
    """Open an image, or turn the first page of a PDF into an image."""
    if getattr(file, "name", "").lower().endswith(".pdf"):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        pix = doc[0].get_pixmap(dpi=200)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return Image.open(file)

st.set_page_config(page_title="Medical Report Explainer", page_icon="🩺", layout="wide")

DISCLAIMER = (
    "⚠️ **This is not medical advice or a diagnosis.** This tool only explains what is "
    "written on your report in simple language. Only a doctor can tell you what your "
    "results mean for your health."
)

LABELS = {"low": "⬇ Low", "high": "⬆ High", "normal": "✓ Normal", "unknown": "? Not checked"}
COLORS = {"low": "#fff3cd", "high": "#f8d7da", "normal": "#d1e7dd", "unknown": "#e2e3e5"}
ORDER = {"high": 0, "low": 1, "unknown": 2, "normal": 3}


def fmt_range(low, high):
    if low is None and high is None:
        return "—"
    if low is None:
        return f"up to {high:g}"
    if high is None:
        return f"{low:g} and above"
    return f"{low:g} – {high:g}"


def build_table(tests):
    rows = []
    for t, res in zip(tests, resolve_statuses(tests)):
        status = res["status"]
        rows.append({
            "Test": t.get("name", ""),
            "Your value": f"{t.get('value', '')} {t.get('unit') or ''}".strip(),
            "Normal range": fmt_range(res["min"], res["max"]),
            "Status": LABELS[status],
            "What it measures": t.get("what_it_measures", ""),
            "Range source": res["source"],
            "_status": status,
        })
    rows.sort(key=lambda r: ORDER[r["_status"]])
    return pd.DataFrame(rows)


def color_rows(row):
    color = COLORS[row["_status"]]
    return [f"background-color: {color}; color: black"] * len(row)


# ---------------- UI ----------------
st.title("🩺 Medical Report Explainer")
st.caption("Upload a photo of a lab report or prescription and get a simple explanation.")
st.warning(DISCLAIMER)

tab_upload, tab_camera = st.tabs(["📁 Upload photo", "📷 Use camera"])
with tab_upload:
    uploaded = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png", "webp", "pdf"])
with tab_camera:
    camera = st.camera_input("Take a photo of the report")

file = uploaded or camera

if file:
    image = load_image(file)
    st.image(image, caption="Your document", width=350)

    if st.button("Explain my report", type="primary"):
        with st.spinner("Reading your report..."):
            try:
                st.session_state["result"] = analyze_report(image)
            except Exception as e:
                st.session_state.pop("result", None)
                st.error(f"Something went wrong: {e}. Try a clearer photo or try again in a minute.")

result = st.session_state.get("result")

if result:
    st.divider()

    if result.get("report_type") == "unknown":
        st.error("This doesn't look like a lab report or prescription. Please upload a clearer photo.")
        st.stop()

    st.subheader("📝 Summary")
    st.write(result.get("summary", ""))

    tests = result.get("tests") or []
    if tests:
        df = build_table(tests)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("⬆ High", int((df["_status"] == "high").sum()))
        c2.metric("⬇ Low", int((df["_status"] == "low").sum()))
        c3.metric("✓ Normal", int((df["_status"] == "normal").sum()))
        c4.metric("? Not checked", int((df["_status"] == "unknown").sum()))

        st.subheader("🔬 Your results")
        st.caption("Values outside the normal range are shown first and highlighted. "
                   "Please compare with your original report.")
        styled = df.style.apply(color_rows, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True,
                     column_config={"_status": None})

    meds = result.get("medicines") or []
    if meds:
        st.subheader("💊 Medicines")
        meds_df = pd.DataFrame(meds).rename(columns={
            "name": "Medicine", "dosage": "Dosage", "frequency": "How often",
            "duration": "For how long", "what_it_is_for_simple": "What it is generally used for",
        })
        st.dataframe(meds_df, use_container_width=True, hide_index=True)

    questions = result.get("questions_for_doctor") or []
    if questions:
        st.subheader("❓ Questions to ask your doctor")
        for q in questions:
            st.markdown(f"- {q}")

    st.divider()
    st.info(DISCLAIMER)