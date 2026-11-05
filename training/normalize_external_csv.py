import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import argparse
import pandas as pd

def main():
    p=argparse.ArgumentParser(description='Map a generic fake-news CSV into the project schema.')
    p.add_argument('--input',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--title-col',default='title')
    p.add_argument('--text-col',default='text')
    p.add_argument('--label-col',default='label')
    p.add_argument('--fake-value',default='1')
    a=p.parse_args()
    df=pd.read_csv(a.input).fillna('')
    if a.title_col not in df or a.text_col not in df or a.label_col not in df:
        raise SystemExit('Input must contain title/text/label columns or pass the appropriate --*-col options.')
    labels=df[a.label_col].astype(str).str.lower().map(lambda x: 1 if x==str(a.fake_value).lower() or x in {'fake','false','1'} else 0)
    out=pd.DataFrame({'sample_id':[f'EXT_{i:08d}' for i in range(len(df))], 'title':df[a.title_col].astype(str), 'text':df[a.text_col].astype(str), 'label':labels.astype(int), 'source':'external','published_date':'','dataset_source':'external'})
    out.to_csv(a.output,index=False)
    print(f'Wrote {len(out)} normalized rows to {a.output}')
if __name__=='__main__': main()
