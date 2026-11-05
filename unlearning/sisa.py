from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import time
import hashlib
import joblib
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, f1_score
from config import SISA_SHARDS, SISA_SLICES, RANDOM_STATE

@dataclass
class SISAEnsemble:
    version_id: str
    shard_models: list
    vectorizer_params: dict

    def predict_fake_probability(self, texts):
        probs = []
        for item in self.shard_models:
            if item is None:
                continue
            vec = HashingVectorizer(**self.vectorizer_params)
            X = vec.transform(texts)
            model = item['model']
            p = model.predict_proba(X)[:, 1]
            probs.append(p)
        if not probs:
            raise RuntimeError('No trained SISA shard models available.')
        return np.mean(np.vstack(probs), axis=0)

def _make_model(random_state=RANDOM_STATE):
    return SGDClassifier(
        loss='log_loss',
        alpha=1e-5,
        max_iter=1,
        tol=None,
        random_state=random_state,
        learning_rate='optimal'
    )

def _vectorizer_params():
    return {
        'n_features': 2**18,
        'alternate_sign': False,
        'ngram_range': (1, 2),
        'strip_accents': 'unicode',
        'lowercase': True,
        'norm': 'l2'
    }

def _sample_shard(sample_id: str, n_shards: int) -> int:
    return int(hashlib.sha256(sample_id.encode()).hexdigest()[:8], 16) % n_shards

def _slice_frames(df: pd.DataFrame, n_slices: int):
    chunks = np.array_split(df, n_slices)
    return [c.reset_index(drop=True) for c in chunks if len(c)]

def prepare_sisa_data(df: pd.DataFrame, root: Path, n_shards=SISA_SHARDS, n_slices=SISA_SLICES):
    root.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    required = {'sample_id', 'title', 'text', 'label'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    df['sample_id'] = df['sample_id'].astype(str)
    df['text_input'] = (df['title'].fillna('').astype(str) + ' ' + df['text'].fillna('').astype(str)).str.strip()
    df['shard_id'] = df['sample_id'].map(lambda x: _sample_shard(x, n_shards))
    manifest = {'n_shards': n_shards, 'n_slices': n_slices, 'vectorizer': _vectorizer_params(), 'shards': []}
    for shard_id in range(n_shards):
        sdf = df[df.shard_id == shard_id].sort_values('sample_id').reset_index(drop=True)
        shard_csv = root / f'shard_{shard_id}.csv'
        sdf.to_csv(shard_csv, index=False)
        slices = _slice_frames(sdf, n_slices)
        slice_paths = []
        for slice_id, chunk in enumerate(slices):
            p = root / f'shard_{shard_id}_slice_{slice_id}.csv'
            chunk.to_csv(p, index=False)
            slice_paths.append({'slice_id': slice_id, 'path': p.name, 'sample_ids': chunk.sample_id.tolist()})
        manifest['shards'].append({'shard_id': shard_id, 'csv': shard_csv.name, 'slices': slice_paths})
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest

def train_sisa(df: pd.DataFrame, root: Path, version_id: str, n_shards=SISA_SHARDS, n_slices=SISA_SLICES):
    manifest = prepare_sisa_data(df, root, n_shards, n_slices)
    vec_params = manifest['vectorizer']
    shard_models = []
    start_all = time.perf_counter()
    for shard in manifest['shards']:
        model = _make_model(RANDOM_STATE + shard['shard_id'])
        first = True
        checkpoints = []
        slices = shard['slices']
        for slice_meta in slices:
            chunk = pd.read_csv(root / slice_meta['path'])
            vec = HashingVectorizer(**vec_params)
            X = vec.transform(chunk['text_input'].tolist())
            y = chunk['label'].astype(int).to_numpy()
            model.partial_fit(X, y, classes=np.array([0, 1]) if first else None)
            first = False
            cp = root / f'{version_id}_shard_{shard["shard_id"]}_after_slice_{slice_meta["slice_id"]}.joblib'
            joblib.dump(model, cp)
            checkpoints.append(cp.name)
        final_path = root / f'{version_id}_shard_{shard["shard_id"]}_final.joblib'
        joblib.dump(model, final_path)
        shard_models.append({'model_path': final_path.name, 'checkpoints': checkpoints, 'shard_id': shard['shard_id']})
    manifest['version_id'] = version_id
    manifest['shard_models'] = shard_models
    manifest['training_seconds'] = time.perf_counter() - start_all
    active = root / 'active_manifest.json'
    active.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest

def load_active_ensemble(root: Path) -> SISAEnsemble:
    active = root / 'active_manifest.json'
    if not active.exists():
        raise FileNotFoundError('No active SISA model. Train it first.')
    manifest = json.loads(active.read_text(encoding='utf-8'))
    models = []
    for item in manifest['shard_models']:
        p = root / item['model_path']
        if p.exists():
            models.append({'model': joblib.load(p), 'shard_id': item['shard_id']})
    return SISAEnsemble(manifest['version_id'], models, manifest['vectorizer'])

def locate_sample(root: Path, sample_id: str):
    manifest = json.loads((root / 'active_manifest.json').read_text(encoding='utf-8'))
    for shard in manifest['shards']:
        for s in shard['slices']:
            if sample_id in s['sample_ids']:
                return shard['shard_id'], s['slice_id']
    return None

def unlearn_sample(root: Path, sample_id: str, new_version: str):
    """SISA-style selective unlearning: restore the last checkpoint before the affected slice,
    then replay only the affected shard from that slice onward while excluding the forget sample.
    """
    active = json.loads((root / 'active_manifest.json').read_text(encoding='utf-8'))
    location = locate_sample(root, sample_id)
    if location is None:
        raise ValueError(f'Sample {sample_id} is not present in the active SISA manifest.')
    shard_id, forget_slice = location
    shard_meta = next(s for s in active['shards'] if s['shard_id'] == shard_id)
    slices = shard_meta['slices']
    start = time.perf_counter()
    vec_params = active['vectorizer']

    if forget_slice == 0:
        model = _make_model(RANDOM_STATE + shard_id)
        first = True
    else:
        checkpoint_name = active['shard_models'][shard_id]['checkpoints'][forget_slice - 1]
        model = joblib.load(root / checkpoint_name)
        first = False

    new_checkpoints = []
    for idx in range(forget_slice, len(slices)):
        chunk = pd.read_csv(root / slices[idx]['path'])
        chunk = chunk[chunk['sample_id'].astype(str) != str(sample_id)]
        if len(chunk):
            vec = HashingVectorizer(**vec_params)
            X = vec.transform(chunk['text_input'].tolist())
            y = chunk['label'].astype(int).to_numpy()
            model.partial_fit(X, y, classes=np.array([0, 1]) if first else None)
            first = False
        cp = root / f'{new_version}_shard_{shard_id}_after_slice_{idx}.joblib'
        joblib.dump(model, cp)
        new_checkpoints.append(cp.name)

    final = root / f'{new_version}_shard_{shard_id}_final.joblib'
    joblib.dump(model, final)

    new_manifest = dict(active)
    new_manifest['version_id'] = new_version
    new_manifest['training_seconds'] = time.perf_counter() - start
    new_models = []
    for item in active['shard_models']:
        item_copy = dict(item)
        if item_copy['shard_id'] == shard_id:
            item_copy['model_path'] = final.name
            old_cps = item_copy.get('checkpoints', [])
            cps = list(old_cps[:forget_slice]) + new_checkpoints
            item_copy['checkpoints'] = cps
        new_models.append(item_copy)
    new_manifest['shard_models'] = new_models
    new_manifest['unlearned_sample_id'] = sample_id
    new_manifest['affected_shard'] = shard_id
    new_manifest['affected_slice'] = forget_slice
    (root / 'active_manifest.json').write_text(json.dumps(new_manifest, indent=2), encoding='utf-8')
    return new_manifest, time.perf_counter() - start
