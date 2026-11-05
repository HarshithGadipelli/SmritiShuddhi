import argparse, random
from pathlib import Path
import pandas as pd

REAL_TEMPLATES = [
    ('Weather department releases rainfall outlook', 'The national weather department released a seasonal rainfall outlook and advised residents to follow official local forecasts.'),
    ('University announces scholarship deadline', 'The university published an official notice saying scholarship applications will close at the end of the month.'),
    ('Central bank publishes policy statement', 'The central bank released a policy statement describing its current interest-rate decision and economic outlook.'),
    ('City opens new public library', 'The city administration announced the opening of a new public library with reading rooms and digital services.'),
    ('Health department issues vaccination reminder', 'The public health department reminded eligible residents about routine vaccination appointments through its official bulletin.'),
    ('Railway adds weekend service', 'The railway authority announced an additional weekend service on a busy route and published the timetable.'),
]
FAKE_TEMPLATES = [
    ('Government will give every citizen a free luxury phone tomorrow', 'A viral message claims that every citizen will receive a free luxury smartphone tomorrow after a secret nationwide order.'),
    ('Scientists confirm drinking hot water makes people live forever', 'A social post claims scientists have proven that drinking hot water every morning guarantees immortality and eliminates ageing.'),
    ('All exams cancelled forever starting next week', 'A message circulating online claims that every school and university examination has been cancelled permanently from next week without any official notice.'),
    ('Bank transfers will become unlimited and tax free overnight', 'A viral post claims all bank transfers will become unlimited and completely tax free overnight because of a hidden policy.'),
    ('Moon will appear twice tonight according to secret agency', 'An anonymous post claims a secret agency has confirmed that the moon will appear twice in the sky tonight.'),
    ('Government bans rainfall after 9 PM', 'A viral message claims the government has introduced a nationwide ban preventing rainfall after 9 PM.'),
]

def main(rows):
    random.seed(42)
    records=[]
    per=rows//2
    for i in range(per):
        t=REAL_TEMPLATES[i%len(REAL_TEMPLATES)]
        records.append({'sample_id':f'SYN_R_{i:05d}','title':t[0], 'text':t[1]+' This example is synthetic demo training content.', 'label':0, 'source':'synthetic','published_date':'2025-01-01','dataset_source':'demo'})
    for i in range(per):
        t=FAKE_TEMPLATES[i%len(FAKE_TEMPLATES)]
        records.append({'sample_id':f'SYN_F_{i:05d}','title':t[0], 'text':t[1]+' This example is synthetic demo training content.', 'label':1, 'source':'synthetic','published_date':'2025-01-01','dataset_source':'demo'})
    random.shuffle(records)
    df=pd.DataFrame(records)
    Path('data/processed').mkdir(parents=True, exist_ok=True)
    Path('data/demo').mkdir(parents=True, exist_ok=True)
    df.to_csv('data/demo/demo_news.csv', index=False)
    # Keep a training and test copy for immediate execution.
    split=int(len(df)*0.8)
    df.iloc[:split].to_csv('data/processed/train.csv', index=False)
    df.iloc[split:].to_csv('data/processed/test.csv', index=False)
    print(f'Created {len(df)} demo rows: {split} train, {len(df)-split} test')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--rows', type=int, default=1200); a=ap.parse_args(); main(a.rows)
