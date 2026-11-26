import argparse
import csv
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

import openpyxl
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import PROCESSED_DIR, RANDOM_STATE  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
OFFICIAL_CORPUS_PATH = ROOT / "data" / "official_corpus" / "verified_truth_corpus.json"
DEFAULT_DOWNLOADS = Path(r"C:\Users\Harshith Gadipelli\Downloads")

FACTCHECK_PREFIX_RE = re.compile(
    r"^\s*(?:fact[\s\-]*check|factcheck|fake\s*news|padtaal|investigation|viral\s*test|read\s*fact\s*check)\s*[:\-–|]\s*",
    flags=re.IGNORECASE,
)


def _clean_text(val: object) -> str:
    if val is None:
        return ""
    s = html.unescape(str(val))
    s = s.replace("\ufffd", " ").replace("\xa0", " ").replace("\u200b", "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_factcheck_prefix(s: str) -> str:
    cleaned = FACTCHECK_PREFIX_RE.sub("", _clean_text(s)).strip()
    return cleaned


def _infer_category(text: str, hint: str = "") -> str:
    low = f"{hint} {text}".lower()
    if any(k in low for k in ("rbi", "rupee", "bank", "gst", "tax", "sebi", "upi", "gdp", "sensex", "budget", "market", "inflation", "acq")):
        return "Finance"
    if any(k in low for k in ("isro", "ai", "cyber", "telecom", "5g", "quantum", "vaccine", "covid", "health", "aiims", "who", "medical")):
        return "Tech & Health" if "health" not in hint.lower() else "Health"
    if any(k in low for k in ("army", "border", "defence", "defense", "missile", "lac", "navy", "iaf")):
        return "Defense"
    if any(k in low for k in ("cricket", "ipl", "bcci", "fifa", "olympic", "sport", "match")):
        return "Sports"
    if any(k in low for k in ("election", "parliament", "modi", "rahul", "bjp", "congress", "cabinet", "minister", "cm ", "supreme court", "eci")):
        return "Politics"
    return "General"


def _download_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-CorpusBuilder/2.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    return dest


def download_liar_plus() -> Tuple[pd.DataFrame, pd.DataFrame]:
    liar_dir = RAW_DIR / "liar_plus"
    base_url = "https://raw.githubusercontent.com/Tariq60/LIAR-PLUS/master/dataset/tsv"
    files = ["train2.tsv", "val2.tsv", "test2.tsv"]
    dfs = []
    for fname in files:
        dest = _download_file(f"{base_url}/{fname}", liar_dir / fname)
        df = pd.read_csv(dest, sep="\t", header=None, on_bad_lines="skip")
        dfs.append(df)
    full = pd.concat(dfs, ignore_index=True)

    # Columns: 0=idx, 1=json_id, 2=label, 3=statement, 4=subject, 5=speaker, 8=party, 14=context, 15=justification
    binary_map = {
        "true": 0,
        "mostly-true": 0,
        "false": 1,
        "barely-true": 1,
        "pants-fire": 1,
    }
    records = []
    half_truth_records = []
    for idx, row in full.iterrows():
        raw_lbl = str(row.iloc[2]).strip().lower() if len(row) > 2 else ""
        stmt = _clean_text(row.iloc[3] if len(row) > 3 else "")
        subj = _clean_text(row.iloc[4] if len(row) > 4 else "")
        speaker = _clean_text(row.iloc[5] if len(row) > 5 else "")
        ctx = _clean_text(row.iloc[14] if len(row) > 14 else "")
        if len(stmt) < 20:
            continue
        body = f"{stmt}. Subject: {subj}. Context: {ctx or 'Public statement'}."
        title = stmt[:110]
        if raw_lbl == "half-true":
            half_truth_records.append(
                {
                    "sample_id": f"LIARP_HALF_{idx:05d}",
                    "title": title,
                    "text": body,
                    "raw_label": "half-true",
                    "speaker": speaker,
                    "subject": subj,
                    "source": "LIAR-PLUS",
                }
            )
            continue
        if raw_lbl in binary_map:
            records.append(
                {
                    "sample_id": f"LIARP_{idx:05d}",
                    "title": title,
                    "text": body,
                    "label": binary_map[raw_lbl],
                    "source": speaker or "PolitiFact",
                    "published_date": "2020-01-01",
                    "dataset_source": "LIAR-PLUS",
                    "category": _infer_category(body, subj),
                }
            )
    return pd.DataFrame(records), pd.DataFrame(half_truth_records)


def download_welfake_sample(target_per_class: int = 1250) -> pd.DataFrame:
    cache_path = RAW_DIR / "welfake_sample.csv"
    if cache_path.exists() and cache_path.stat().st_size > 100_000:
        df = pd.read_csv(cache_path)
        if len(df) >= target_per_class * 2 - 100:
            return df

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    reals: List[Dict] = []
    fakes: List[Dict] = []
    # WELFake has ~72k rows; sample strided offsets for broad topical diversity.
    offsets = list(range(0, 32000, 700))
    for off in offsets:
        if len(reals) >= target_per_class and len(fakes) >= target_per_class:
            break
        url = (
            "https://datasets-server.huggingface.co/rows"
            f"?dataset=davanstrien/WELFake&config=default&split=train&offset={off}&length=100"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-CorpusBuilder/2.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
        for item in data.get("rows", []):
            row = item.get("row") or {}
            lbl = row.get("label")
            if lbl not in (0, 1):
                continue
            title = _clean_text(row.get("title") or "")
            body = _clean_text(row.get("text") or "")
            if len(title) < 12 or len(body) < 80:
                continue
            rec = {
                "sample_id": f"WEL_{item.get('row_idx', off):06d}",
                "title": title[:220],
                "text": body[:1600],
                "label": int(lbl),
                "source": "WELFake-Wire" if int(lbl) == 0 else "WELFake-Unverified",
                "published_date": "2019-06-01",
                "dataset_source": "WELFake",
                "category": _infer_category(f"{title} {body[:300]}"),
            }
            if int(lbl) == 0 and len(reals) < target_per_class:
                reals.append(rec)
            elif int(lbl) == 1 and len(fakes) < target_per_class:
                fakes.append(rec)

    df = pd.DataFrame(reals + fakes).drop_duplicates(subset=["title"]).reset_index(drop=True)
    df.to_csv(cache_path, index=False)
    return df


def fetch_pib_factcheck_rss() -> Tuple[pd.DataFrame, List[Dict]]:
    cache_path = RAW_DIR / "pib_factcheck_rss.json"
    items: List[Dict] = []
    queries = [
        "PIB Fact Check viral claim",
        "PIB Fact Check fake message RBI government",
        "Press Information Bureau India official release",
    ]
    for q in queries:
        encoded = urllib.parse.quote_plus(q)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-CorpusBuilder/2.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_bytes = resp.read()
            root = ET.fromstring(xml_bytes)
            for node in root.findall("./channel/item"):
                title = _clean_text(node.findtext("title") or "")
                link = _clean_text(node.findtext("link") or "")
                pub = _clean_text(node.findtext("pubDate") or "")
                desc = _clean_text(node.findtext("description") or "")
                src_el = node.find("source")
                src = _clean_text(src_el.text if src_el is not None else "GoogleNews-PIB")
                if title:
                    items.append(
                        {
                            "title": title,
                            "description": desc,
                            "link": link,
                            "published_date": pub,
                            "source": src,
                            "query": q,
                        }
                    )
        except Exception:
            continue

    if items:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    elif cache_path.exists():
        items = json.loads(cache_path.read_text(encoding="utf-8"))

    train_rows = []
    corpus_docs = []
    for idx, it in enumerate(items[:140]):
        title = _strip_factcheck_prefix(it["title"].rsplit(" - ", 1)[0])
        desc = _clean_text(it["description"])
        is_debunk = any(
            kw in (it["title"] + " " + desc + " " + it["query"]).lower()
            for kw in ("fact check", "fake", "pib fact check", "hoax", "misleading", "false claim")
        )
        if is_debunk and len(title) >= 20:
            train_rows.append(
                {
                    "sample_id": f"PIB_FC_{idx:04d}",
                    "title": title[:220],
                    "text": f"{title}. {desc}"[:1000],
                    "label": 1,
                    "source": "PIB Fact Check",
                    "published_date": it["published_date"][:25] or "2025-01-01",
                    "dataset_source": "PIB_FactCheck",
                    "category": _infer_category(title),
                }
            )
            corpus_docs.append(
                {
                    "doc_id": f"CORP_PIB_{idx:04d}",
                    "title": title[:200],
                    "text": f"Official PIB / News Fact-Check Reference: {title}. {desc[:380]}",
                    "source": it.get("source") or "PIB Fact Check",
                    "url": it.get("link") or "https://factcheck.pib.gov.in",
                    "published_date": it.get("published_date") or "2025-01-01",
                    "truth_status": "VERIFIED_DEBUNK",
                    "category": _infer_category(title),
                }
            )
    return pd.DataFrame(train_rows), corpus_docs


def load_ifnd(downloads_dir: Path, per_class: int = 1500) -> pd.DataFrame:
    path = downloads_dir / "IFND.csv"
    if not path.exists():
        return pd.DataFrame()
    reals: List[Dict] = []
    fakes: List[Dict] = []
    seen = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        rdr = csv.DictReader(f)
        for idx, row in enumerate(rdr):
            raw_lbl = (row.get("Label") or "").strip()
            raw_stmt = _clean_text(row.get("Statement") or "")
            stmt = _strip_factcheck_prefix(raw_stmt)
            if len(stmt) < 25 or stmt.lower() in seen:
                continue
            seen.add(stmt.lower())
            web = _clean_text(row.get("Web") or "IFND")
            cat = _clean_text(row.get("Category") or "")
            dt = _clean_text(row.get("Date") or "2021-01-01") or "2021-01-01"
            if raw_lbl == "TRUE" and len(reals) < per_class:
                reals.append(
                    {
                        "sample_id": f"IFND_R_{idx:06d}",
                        "title": stmt[:200],
                        "text": f"{stmt}. Reported by {web} under {cat or 'India News'} coverage.",
                        "label": 0,
                        "source": web,
                        "published_date": dt,
                        "dataset_source": "IFND",
                        "category": _infer_category(stmt, cat),
                    }
                )
            elif raw_lbl == "Fake" and len(fakes) < per_class:
                # Avoid trivial debunk phrasing artifacts ("No, ..." or pure questions) where possible
                if stmt.lower().startswith(("no,", "no ", "did ")):
                    continue
                fakes.append(
                    {
                        "sample_id": f"IFND_F_{idx:06d}",
                        "title": stmt[:200],
                        "text": f"{stmt}. Unverified viral claim flagged during {cat or 'Indian media'} review.",
                        "label": 1,
                        "source": web if web != "AUGMENT" else "Viral-Forward",
                        "published_date": dt,
                        "dataset_source": "IFND",
                        "category": _infer_category(stmt, cat),
                    }
                )
            if len(reals) >= per_class and len(fakes) >= per_class:
                break
    return pd.DataFrame(reals + fakes)


def load_bharat_fakenewskosh(downloads_dir: Path, max_train: int = 1000, max_corpus: int = 120) -> Tuple[pd.DataFrame, List[Dict]]:
    path = downloads_dir / "bharatfakenewskosh.xlsx"
    if not path.exists():
        return pd.DataFrame(), []
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    hdr = list(next(rows_iter))
    idx_map = {name: i for i, name in enumerate(hdr)}

    train_rows: List[Dict] = []
    corpus_docs: List[Dict] = []
    seen = set()
    for idx, row in enumerate(rows_iter):
        stmt = _strip_factcheck_prefix(row[idx_map.get("Eng_Trans_Statement", 5)] or row[idx_map.get("Statement", 4)] or "")
        body = _clean_text(row[idx_map.get("Eng_Trans_News_Body", 7)] or row[idx_map.get("News Body", 6)] or "")
        src = _clean_text(row[idx_map.get("Fact_Check_Source", 2)] or "IFCN-India")
        link = _clean_text(row[idx_map.get("Fact_Check_Link", 10)] or "")
        cat = _clean_text(row[idx_map.get("News_Category", 11)] or "")
        dt = _clean_text(row[idx_map.get("Publish_Date", 9)] or "2022-06-01")
        lang = _clean_text(row[idx_map.get("Language", 12)] or "English")

        if len(stmt) < 28 or stmt.lower() in seen:
            continue
        # Only take high-confidence verified debunks from IFCN / Indian fact-checkers
        if not any(tok in (link + " " + body).lower() for tok in ("false", "fake", "old", "morphed", "doctored", "mislead", "fact-check", "factcheck", "wrong", "hoax")):
            continue
        seen.add(stmt.lower())

        if len(corpus_docs) < max_corpus and lang.lower() == "english":
            corpus_docs.append(
                {
                    "doc_id": f"CORP_BFK_{idx:05d}",
                    "title": stmt[:200],
                    "text": f"IFCN Verified Debunk ({src}): {stmt}. {body[:420]}",
                    "source": src,
                    "url": link or "https://www.altnews.in",
                    "published_date": dt[:20] or "2022-06-01",
                    "truth_status": "VERIFIED_DEBUNK",
                    "category": _infer_category(stmt, cat),
                }
            )

        if len(train_rows) < max_train and not stmt.lower().startswith(("no,", "no ", "did ", "was ", "is ")):
            snippet = body[:550] if body else stmt
            train_rows.append(
                {
                    "sample_id": f"BFNK_{idx:06d}",
                    "title": stmt[:200],
                    "text": f"{stmt}. {snippet}"[:1200],
                    "label": 1,
                    "source": "Social-Viral-Unverified",
                    "published_date": dt[:20] or "2022-06-01",
                    "dataset_source": "BharatFakeNewsKosh",
                    "category": _infer_category(stmt, cat),
                }
            )
        if len(train_rows) >= max_train and len(corpus_docs) >= max_corpus:
            break
    wb.close()
    return pd.DataFrame(train_rows), corpus_docs


def load_reuters_india(downloads_dir: Path, max_rows: int = 1000) -> pd.DataFrame:
    path = downloads_dir / "ReutersIndia json" / "train.json"
    if not path.exists():
        return pd.DataFrame()
    raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    india_first = []
    other_rows = []
    for idx, item in enumerate(raw):
        title = _clean_text(item.get("title") or "")
        body = _clean_text(item.get("text") or "")
        if len(title) < 12 or len(body) < 60:
            continue
        places = " ".join(str(p).lower() for p in (item.get("places") or []))
        topics = " ".join(str(t) for t in (item.get("topics") or []))
        rec = {
            "sample_id": f"REUT_{idx:06d}",
            "title": title[:220],
            "text": body[:1500],
            "label": 0,
            "source": "Reuters",
            "published_date": "2020-01-01",
            "dataset_source": "ReutersIndia",
            "category": _infer_category(f"{title} {body[:200]}", topics),
        }
        if "india" in places or "india" in body.lower() or "rupee" in body.lower():
            india_first.append(rec)
        else:
            other_rows.append(rec)
    selected = (india_first + other_rows)[:max_rows]
    return pd.DataFrame(selected)


def build_official_baseline_corpus() -> Tuple[pd.DataFrame, List[Dict]]:
    official_facts = [
        ("CORP_RBI_500_2026", "RBI Official Notification on Currency Notes Validity", "The Reserve Bank of India confirms Rs 500 denomination Mahatma Gandhi New Series banknotes remain legal tender nationwide with no ban or cancellation circular.", "RBI", "Finance"),
        ("CORP_ISRO_CH3_2023", "ISRO Chandrayaan-3 Historic South Pole Soft Landing", "ISRO successfully landed Chandrayaan-3 Vikram lander near the Moon South Polar region on August 23, 2023, deployed Pragyan rover, and executed in-situ elemental analysis.", "ISRO", "Tech & Health"),
        ("CORP_ISRO_ADITYA_L1", "ISRO Aditya-L1 Solar Observatory Positioned at L1", "ISRO inserted Aditya-L1 into a halo orbit around the Sun-Earth Lagrange Point L1 in January 2024 to monitor coronal mass ejections and solar wind.", "ISRO", "Tech & Health"),
        ("CORP_UPI_FREE_P2P", "NPCI Confirms Zero Merchant Fee on Standard P2P UPI Payments", "NPCI and RBI reiterated that bank-to-bank person-to-person UPI transfers remain free for everyday citizens and PPI interchange applies only above Rs 2,000 wallets.", "NPCI / RBI", "Finance"),
        ("CORP_UIDAI_AADHAAR", "UIDAI Clarification on Masked Aadhaar & Biometric Locks", "UIDAI clarifies citizens can lock biometrics via mAadhaar app at zero fee and no automated citizenship revocation or SIM deactivation occurs via SMS links.", "UIDAI", "General"),
        ("CORP_ECI_VVPAT", "Election Commission of India Mandatory 5% VVPAT Verification", "Supreme Court and Election Commission of India mandates randomized physical counting of VVPAT paper slips across five polling stations per Assembly constituency alongside EVMs.", "ECI", "Politics"),
        ("CORP_IMD_FORECAST", "India Meteorological Department Official Severe Weather Bulletins", "IMD issues color-coded monsoon, cyclone, and heatwave alerts directly on mausam.imd.gov.in without attributing rain events to satellite bans or secret HAARP tests.", "IMD", "General"),
        ("CORP_PIB_FREE_PHONE", "PIB Fact Check Debunk on Free Government Laptop and Phone Links", "Viral WhatsApp messages promising free smartphones, cash doles, or 5G recharge under spurious Pradhan Mantri links are phishing scams not backed by any Ministry.", "PIB Fact Check", "Politics"),
    ]
    train_real = []
    corpus_docs = []
    for cid, title, text, src, cat in official_facts:
        status = "VERIFIED_DEBUNK" if "Debunk" in title or "PIB Fact Check" in src else "VERIFIED_FACT"
        corpus_docs.append(
            {
                "doc_id": cid,
                "title": title,
                "text": text,
                "source": src,
                "url": "https://pib.gov.in",
                "published_date": "2025-01-15",
                "truth_status": status,
                "category": cat,
            }
        )
        if status == "VERIFIED_FACT":
            train_real.append(
                {
                    "sample_id": f"OFF_{cid}",
                    "title": title,
                    "text": text,
                    "label": 0,
                    "source": src,
                    "published_date": "2025-01-15",
                    "dataset_source": "IndianTruthCorpus",
                    "category": cat,
                }
            )
    return pd.DataFrame(train_real), corpus_docs


def main():
    parser = argparse.ArgumentParser(description="Build unified real multi-source corpus for Smriti Shuddhi.")
    parser.add_argument("--downloads-dir", type=Path, default=DEFAULT_DOWNLOADS)
    parser.add_argument("--test-size", type=float, default=0.20)
    args = parser.parse_args()

    print("1/6 Downloading & loading LIAR-PLUS...")
    liar_df, half_truth_df = download_liar_plus()
    print(f"   LIAR-PLUS binary={len(liar_df)}, half-true heldout={len(half_truth_df)}")

    print("2/6 Downloading & loading WELFake balanced sample...")
    welfake_df = download_welfake_sample(target_per_class=1250)
    print(f"   WELFake rows={len(welfake_df)}")

    print("3/6 Fetching Google News PIB Fact Check RSS...")
    pib_df, pib_corpus = fetch_pib_factcheck_rss()
    print(f"   PIB RSS fake={len(pib_df)}, corpus={len(pib_corpus)}")

    print("4/6 Loading IFND, BharatFakeNewsKosh, ReutersIndia & Official Indian Truth baselines...")
    ifnd_df = load_ifnd(args.downloads_dir, per_class=1500)
    bfk_df, bfk_corpus = load_bharat_fakenewskosh(args.downloads_dir, max_train=1000, max_corpus=120)
    reuters_df = load_reuters_india(args.downloads_dir, max_rows=1000)
    official_df, official_corpus = build_official_baseline_corpus()
    print(f"   IFND={len(ifnd_df)}, BFK={len(bfk_df)}, Reuters={len(reuters_df)}, Official={len(official_df)}")

    # Balance LIAR-PLUS up to 1200 per class
    liar_r = liar_df[liar_df["label"] == 0].head(1200)
    liar_f = liar_df[liar_df["label"] == 1].head(1200)

    combined = pd.concat(
        [ifnd_df, bfk_df, reuters_df, welfake_df, liar_r, liar_f, pib_df, official_df],
        ignore_index=True,
    )
    combined = combined.dropna(subset=["title", "text", "label"])
    combined["label"] = combined["label"].astype(int)
    combined["title_norm"] = combined["title"].str.lower().str.strip()
    combined = combined.drop_duplicates(subset=["title_norm"]).drop(columns=["title_norm"])

    # Balance class 0 and class 1 cleanly
    real_df = combined[combined["label"] == 0]
    fake_df = combined[combined["label"] == 1]
    n_bal = min(len(real_df), len(fake_df), 5000)
    balanced = pd.concat(
        [
            real_df.sample(n=n_bal, random_state=RANDOM_STATE),
            fake_df.sample(n=n_bal, random_state=RANDOM_STATE),
        ],
        ignore_index=True,
    ).sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)

    train_df, test_df = train_test_split(
        balanced,
        test_size=args.test_size,
        stratify=balanced["label"],
        random_state=RANDOM_STATE,
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)
    if not half_truth_df.empty:
        half_truth_df.head(500).to_csv(PROCESSED_DIR / "half_truth_eval.csv", index=False)

    all_corpus = official_corpus + pib_corpus + bfk_corpus
    OFFICIAL_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFICIAL_CORPUS_PATH.write_text(json.dumps(all_corpus, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Unified Corpus Summary ===")
    print(f"Train rows: {len(train_df)} | Class balance: {train_df['label'].value_counts().to_dict()}")
    print(f"Test rows:  {len(test_df)} | Class balance: {test_df['label'].value_counts().to_dict()}")
    print(f"Dataset Sources (Train): {train_df['dataset_source'].value_counts().to_dict()}")
    print(f"Half-Truth Heldout rows: {min(len(half_truth_df), 500)}")
    print(f"Official Truth & Debunk Vector Corpus docs: {len(all_corpus)} -> {OFFICIAL_CORPUS_PATH}")


if __name__ == "__main__":
    main()
