import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import argparse
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split
from training.data_utils import load_normalized_csv
from config import RANDOM_STATE, PROCESSED_DIR

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--test-size', type=float, default=0.2)
    args = p.parse_args()
    df = load_normalized_csv(args.input)
    train, test = train_test_split(df, test_size=args.test_size, stratify=df['label'], random_state=RANDOM_STATE)
    train.to_csv(PROCESSED_DIR / 'train.csv', index=False)
    test.to_csv(PROCESSED_DIR / 'test.csv', index=False)
    print(f'Train: {len(train)}')
    print(f'Test: {len(test)}')
