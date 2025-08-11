import io
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

# ---------- Helpers ----------

def read_any_table(upload):
    if upload is None:
        return None
    name = upload.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(upload)
    if name.endswith(".tsv") or name.endswith(".txt"):
        return pd.read_csv(upload, sep="\t")
    return pd.read_excel(upload)

def normalize_apn(apn: str) -> str:
    s = str(apn or "").strip()
    for ch in [" ", "-", "_", "/", "."]:
        s = s.replace(ch, "")
    return s.lower()

def addr_query(address, city, state, postal):
    parts = [str(address or "").strip(), str(city or "").strip(), str(state or "").strip(), str(postal or "").strip()]
    parts = [p for p in parts if p]
    return " ".join(parts)

def build_gis_links(row):
    county = str(row.get("County Finder", "") or "")
    state = str(row.get("State", "") or "")
    apn   = str(row.get("APN", "") or "")
    addrq = str(row.get("addr_query", "") or "")

    google_q = f"{county} {state} GIS parcel {apn}".strip()
    bing_q   = google_q
    appraiser_q = f"{county} {state} property appraiser {apn}".strip()

    return pd.Series({
        "GIS_Google": "https://www.google.com/search?q=" + quote_plus(google_q),
        "GIS_Bing":   "https://www.bing.com/search?q=" + quote_plus(bing_q),
        "Appraiser_Search": "https://www.google.com/search?q=" + quote_plus(appraiser_q),
        "GIS_By_Address": "https://www.google.com/search?q=" + quote_plus(f"{county} {state} GIS {addrq}"),
    })

def build_people_osint_links(row):
    addrq = str(row.get("addr_query", "") or "")
    return pd.Series({
        "OSINT_Google_Addr": "https://www.google.com/search?q=" + quote_plus(addrq),
        "OSINT_Bing_Addr":   "https://www.bing.com/search?q=" + quote_plus(addrq),
        "Whitepages":        "https://www.whitepages.com/address/" + addrq.replace(" ", "-"),
        "FastPeopleSearch":  "https://www.fastpeoplesearch.com/address/" + addrq.replace(" ", "-"),
        "BeenVerified":      "https://www.beenverified.com/people/search/?n=&citystatezip=" + quote_plus(addrq),
    })

def build_social_links(row):
    addrq = str(row.get("addr_query", "") or "")
    return pd.Series({
        "Facebook_Search": "https://www.facebook.com/search/top/?q=" + quote_plus(addrq),
        "LinkedIn_Search": "https://www.linkedin.com/search/results/all/?keywords=" + quote_plus(addrq),
        "X_Search":        "https://x.com/search?q=" + quote_plus(addrq) + "&src=typed_query",
    })

def merge_on_apn(base: pd.DataFrame, other: pd.DataFrame, suffix: str) -> pd.DataFrame:
    if other is None or len(other) == 0:
        return base
    df = base.copy()
    pw = other.copy()

    for c in ["APN", "Parcel", "Parcel Number", "parcel", "parcel number"]:
        if c in pw.columns:
            pw.rename(columns={c: "APN"}, inplace=True)
            break
    if "APN" not in pw.columns:
        pw["APN"] = ""

    df["APN_key"] = df["APN"].astype(str).str.replace(r"\W+", "", regex=True).str.lower()
    pw["APN_key"] = pw["APN"].astype(str).str.replace(r"\W+", "", regex=True).str.lower()

    merged = df.merge(pw, how="left", on="APN_key", suffixes=("", suffix))
    return merged.drop(columns=["APN_key"], errors="ignore")

def to_excel_bytes(main_df: pd.DataFrame, meta: dict, batch_name: str) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        main_df.to_excel(writer, sheet_name="enriched", index=False)
        pd.DataFrame([meta]).to_excel(writer, sheet_name="meta", index=False)
        dict_rows = [{"column": c, "example": str(main_df[c].dropna().astype(str).head(1).values[0]) if c in main_df.columns and main_df[c].notna().any() else ""} for c in main_df.columns]
        pd.DataFrame(dict_rows).to_excel(writer, sheet_name="columns", index=False)
    bio.seek(0)
    return bio.read()

# ---------- UI ----------

st.set_page_config(page_title="Surplus Funds OSINT", page_icon="💰", layout="wide")
st.markdown("# 🎮 Surplus Funds OSINT — Research Console")
st.caption("Upload → Enrich → Download. No logins, no scraping headaches.")

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    batch_name = st.text_input("Batch name", value=f"batch_{datetime.now().strftime('%Y%m%d_%H%M')}")

    st.markdown("### 📥 Upload your lead file")
    lead_file = st.file_uploader("CSV / Excel (columns like APN, County, Address, City, State, Zip)", type=["csv","xlsx","xls","tsv","txt"])

    st.markdown("### ➕ Optional: Upload Propwire/PropertyRadar exports")
    propwire_file = st.file_uploader("Propwire export (CSV/XLSX)", type=["csv","xlsx","xls"], key="propwire")
    pradar_file   = st.file_uploader("PropertyRadar export (CSV/XLSX)", type=["csv","xlsx","xls"], key="propertyradar")

    st.markdown("### 🔎 Enrichment toggles")
    use_county = st.checkbox("Generate County GIS lookups", value=True)
    use_osint  = st.checkbox("Generate OSINT people-search links", value=True)
    use_social = st.checkbox("Generate social media dorks", value=True)

    run_btn = st.button("🚀 Run Enrichment", use_co
