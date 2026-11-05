import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pathlib import Path
import json
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from unlearning.sisa import load_active_ensemble
from config import SISA_DIR, EVAL_DIR


def main():
    test_path=Path('data/processed/test.csv')
    if not test_path.exists():
        raise SystemExit('Missing data/processed/test.csv. Run scripts/generate_demo_dataset.py first.')
    df=pd.read_csv(test_path).fillna('')
    texts=(df['title'].astype(str)+' '+df['text'].astype(str)).tolist()
    y=df['label'].astype(int).to_numpy()
    ens=load_active_ensemble(SISA_DIR)
    p=ens.predict_fake_probability(texts)
    pred=(p>=0.5).astype(int)
    out={
      'model_version':ens.version_id,
      'accuracy':accuracy_score(y,pred),
      'precision':precision_score(y,pred,zero_division=0),
      'recall':recall_score(y,pred,zero_division=0),
      'f1':f1_score(y,pred,zero_division=0),
      'roc_auc':roc_auc_score(y,p) if len(set(y))==2 else None
    }
    EVAL_DIR.mkdir(parents=True,exist_ok=True)
    (EVAL_DIR/'base_model_metrics.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))

if __name__=='__main__': main()
