from pathlib import Path
import pandas as pd

def load_normalized_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {'sample_id', 'title', 'text', 'label'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'{path}: missing required columns {sorted(missing)}')
    df = df.copy()
    df['sample_id'] = df['sample_id'].astype(str)
    df['title'] = df['title'].fillna('').astype(str)
    df['text'] = df['text'].fillna('').astype(str)
    df['label'] = df['label'].astype(int)
    if not set(df['label'].unique()).issubset({0, 1}):
        raise ValueError('label must contain only 0 (REAL) and 1 (FAKE).')
    return df.drop_duplicates(subset=['sample_id']).reset_index(drop=True)
