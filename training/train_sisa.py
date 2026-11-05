import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import argparse
from pathlib import Path
from training.data_utils import load_normalized_csv
from unlearning.sisa import train_sisa
from config import SISA_DIR, SISA_SHARDS, SISA_SLICES

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='data/processed/train.csv')
    parser.add_argument('--shards', type=int, default=SISA_SHARDS)
    parser.add_argument('--slices', type=int, default=SISA_SLICES)
    parser.add_argument('--version', default='v1')
    args = parser.parse_args()
    df = load_normalized_csv(args.data)
    manifest = train_sisa(df, SISA_DIR, args.version, args.shards, args.slices)
    print(f'Trained {len(manifest["shards"])} SISA shards.')
    print(f'Version: {manifest["version_id"]}')
    print(f'Time: {manifest["training_seconds"]:.3f}s')
