import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db
from app.retrieval.news_feed import TOPIC_IMAGE_MAP, FALLBACK_IMAGE

count = 0
for it in db.news_col.find({}):
    if not it.get('image_url'):
        cat = it.get('category', 'General')
        img = TOPIC_IMAGE_MAP.get(cat, FALLBACK_IMAGE)
        db.news_col.update_one({'_id': it['_id']}, {'$set': {'image_url': img, 'reading_time': '3 min read'}})
        count += 1
print(f'Updated {count} news items with photography images.')
