import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import argparse
import pandas as pd

LABEL_MAP={'true':0,'mostly-true':0,'half-true':0,'false':1,'barely-true':1,'pants-fire':1}

def main():
    p=argparse.ArgumentParser(description='Normalize a LIAR TSV file into the project schema.')
    p.add_argument('--input',required=True,help='Path to LIAR train/valid/test TSV')
    p.add_argument('--output',required=True)
    a=p.parse_args()
    df=pd.read_csv(a.input,sep='\t',header=None)
    # LIAR columns: id,label,statement,subject,speaker,job_title,state,party,context, ...
    out=pd.DataFrame({
      'sample_id':df.iloc[:,0].astype(str),
      'title':'',
      'text':df.iloc[:,2].astype(str),
      'label':df.iloc[:,1].astype(str).str.lower().map(LABEL_MAP),
      'source':'LIAR',
      'published_date':'',
      'dataset_source':'LIAR'
    })
    out=out.dropna(subset=['label'])
    out['label']=out['label'].astype(int)
    out.to_csv(a.output,index=False)
    print(f'Wrote {len(out)} rows to {a.output}')
if __name__=='__main__': main()
