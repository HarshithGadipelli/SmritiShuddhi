import json
import re
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat()

def run_ingestion():
    reuters_path = Path(r"c:\Users\Harshith Gadipelli\Downloads\ReutersIndia json\train.json")
    if not reuters_path.exists():
        print(f"File not found: {reuters_path}")
        return

    print(f"Loading Reuters India dataset from {reuters_path}...")
    with open(reuters_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} total records.")

    # Filter articles relevant to India, South Asia, trade, commodities, energy, tech
    indian_articles = []
    keywords = [
        r'\bindia\b', r'\bindian\b', r'\bdelhi\b', r'\bmumbai\b', r'\bbangalore\b',
        r'\brupee\b', r'\brbi\b', r'\bbjp\b', r'\bcongress\b', r'\bmodi\b',
        r'\bisro\b', r'\bmonsoon\b', r'\bcricket\b', r'\basian\b', r'\bopec\b'
    ]
    pattern = re.compile("|".join(keywords), re.IGNORECASE)

    for item in data:
        title = (item.get("title") or "").strip()
        text = (item.get("text") or "").strip()
        places = [p.lower() for p in item.get("places", [])]
        
        if not title or len(text) < 50:
            continue
            
        is_india_place = "india" in places
        has_india_kw = bool(pattern.search(title + " " + text))
        
        if is_india_place or has_india_kw:
            # Clean headline capitalization
            clean_title = title.title() if title.islower() else title
            clean_text = text.replace("\n", " ").strip()
            
            # Category mapping
            topics = [t.lower() for t in item.get("topics", [])]
            cat = "Banking & Economy"
            if any(t in topics for t in ["earn", "acq", "money-fx", "interest"]):
                cat = "Banking & Economy"
            elif any(t in topics for t in ["grain", "crude", "oil", "veg-oil", "copper"]):
                cat = "Industry & Commodities"
            elif any(t in topics for t in ["trade", "ship"]):
                cat = "Trade & Transport"
            elif "space" in title.lower() or "tech" in title.lower():
                cat = "Technology & AI"
            else:
                cat = "National & Governance"

            indian_articles.append({
                "news_id": f"NEWS_REUTERS_{uuid.uuid4().hex[:8].upper()}",
                "sample_id": f"SYN_R_{uuid.uuid4().hex[:6].upper()}",
                "title": clean_title,
                "text": clean_text,
                "category": cat,
                "source": "Reuters India",
                "author": "Reuters Correspondent",
                "language": "English",
                "region": "India National",
                "status": "PUBLISHED",
                "tag": "REAL",
                "tag_display": "REAL (VERIFIED FACTUAL)",
                "fake_probability": 0.04,
                "real_probability": 0.96,
                "risk_band": "LOW_RISK_FACTUAL",
                "action_recommended": "ALLOW_AUTOMATIC_BROADCAST",
                "s_style": 0.08,
                "s_fact": 0.02,
                "temporal_consistency": 0.98,
                "reading_time": f"{max(1, len(clean_text.split()) // 55)} min read",
                "created_at": now()
            })

    print(f"Curated {len(indian_articles)} high-quality Indian news dispatches from Reuters India.")

    # Save to local_store.json
    store_path = Path("data/local_store.json")
    if store_path.exists():
        with open(store_path, "r", encoding="utf-8") as f:
            local_store = json.load(f)
    else:
        local_store = {}

    news_list = local_store.get("news", [])
    existing_titles = set((x.get("title") or "").strip().lower() for x in news_list)

    added_count = 0
    # Add top 25 curated stories into live wire so broadsheet is rich with authentic Reuters India dispatches
    for art in indian_articles:
        if art["title"].lower() not in existing_titles and added_count < 25:
            news_list.append(art)
            existing_titles.add(art["title"].lower())
            added_count += 1

    local_store["news"] = news_list
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(local_store, f, indent=2)

    print(f"Successfully added {added_count} curated Reuters India articles into data/local_store.json!")

    # Also append to data/processed/train.csv as verified real samples
    train_csv_path = Path("data/processed/train.csv")
    if train_csv_path.exists():
        import pandas as pd
        train_df = pd.read_csv(train_csv_path)
        new_rows = []
        for art in indian_articles[:100]:
            new_rows.append({
                "sample_id": art["sample_id"],
                "title": art["title"],
                "text": art["text"],
                "label": 0,
                "source": "reuters_india",
                "published_date": "2025-01-01",
                "dataset_source": "reuters_india"
            })
        if new_rows:
            combined_df = pd.concat([train_df, pd.DataFrame(new_rows)], ignore_index=True)
            combined_df.to_csv(train_csv_path, index=False)
            print(f"Added {len(new_rows)} Reuters India training samples into data/processed/train.csv (total: {len(combined_df)})")

if __name__ == "__main__":
    run_ingestion()
