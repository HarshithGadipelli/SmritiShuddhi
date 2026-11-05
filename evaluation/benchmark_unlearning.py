import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import argparse, json, time, shutil
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, f1_score
from config import SISA_DIR, EVAL_DIR, RANDOM_STATE
from training.data_utils import load_normalized_csv
from unlearning.sisa import unlearn_sample, train_sisa, _vectorizer_params, _make_model


def predict_single_model(model, df):
    vec=HashingVectorizer(**_vectorizer_params())
    text=(df['title'].astype(str)+' '+df['text'].astype(str)).tolist()
    p=model.predict_proba(vec.transform(text))[:,1]
    return p

def full_retrain(df, forget_ids):
    start=time.perf_counter()
    retain=df[~df.sample_id.astype(str).isin(set(map(str,forget_ids)))].copy()
    model=_make_model(RANDOM_STATE)
    vec=HashingVectorizer(**_vectorizer_params())
    X=vec.transform((retain.title.astype(str)+' '+retain.text.astype(str)).tolist())
    y=retain.label.astype(int).to_numpy()
    model.partial_fit(X,y,classes=np.array([0,1]))
    return model, time.perf_counter()-start

def main(args):
    df=load_normalized_csv(args.data)
    if args.forget_count >= len(df): raise SystemExit('forget-count is too large')
    forget=df.sample(n=args.forget_count, random_state=RANDOM_STATE)
    forget_ids=forget.sample_id.astype(str).tolist()
    test=load_normalized_csv(args.test)
    # SISA benchmark uses a temporary copy to avoid changing the user's trained active model.
    tmp=Path('artifacts/evaluation/sisa_benchmark_runtime')
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    version='bench_v1'
    train_sisa(df,tmp,version,n_shards=5,n_slices=5)
    start=time.perf_counter()
    current_version=version
    for i,sid in enumerate(forget_ids):
        current_version=f'bench_u_{i}'
        # Only one sample per iterative request in this demonstration.
        unlearn_sample(tmp,sid,current_version)
    sisa_time=time.perf_counter()-start
    # load final model ensemble
    import json, joblib
    man=json.loads((tmp/'active_manifest.json').read_text())
    vec=HashingVectorizer(**man['vectorizer'])
    texts=(test.title.astype(str)+' '+test.text.astype(str)).tolist()
    probs=[]
    for item in man['shard_models']:
        mdl=joblib.load(tmp/item['model_path'])
        probs.append(mdl.predict_proba(vec.transform(texts))[:,1])
    sisa_p=np.mean(np.vstack(probs),axis=0); sisa_pred=(sisa_p>=0.5).astype(int)
    full_model, full_time=full_retrain(df,forget_ids)
    full_p=predict_single_model(full_model,test); full_pred=(full_p>=0.5).astype(int)
    y=test.label.to_numpy()
    out={
      'forget_count':args.forget_count,
      'forget_ids':forget_ids,
      'sisa_unlearning_seconds':sisa_time,
      'full_retraining_seconds':full_time,
      'speedup': full_time/sisa_time if sisa_time>0 else None,
      'sisa_retain_accuracy':accuracy_score(y,sisa_pred),
      'sisa_retain_f1':f1_score(y,sisa_pred,zero_division=0),
      'full_retrain_retain_accuracy':accuracy_score(y,full_pred),
      'full_retrain_retain_f1':f1_score(y,full_pred,zero_division=0)
    }
    EVAL_DIR.mkdir(parents=True,exist_ok=True)
    (EVAL_DIR/f'benchmark_{args.forget_count}.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',default='data/processed/train.csv')
    p.add_argument('--test',default='data/processed/test.csv')
    p.add_argument('--forget-count',type=int,default=1)
    main(p.parse_args())
