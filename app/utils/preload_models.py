"""Pre-caches local HuggingFace models and SISA adapters during Docker image builds."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
MODELS_CACHE = ROOT_DIR / "models_cache"


def ensure_models_cached():
    from huggingface_hub import snapshot_download

    MODELS_CACHE.mkdir(parents=True, exist_ok=True)
    targets = [
        ("BAAI/bge-small-en-v1.5", MODELS_CACHE / "bge-small-en-v1.5"),
        ("microsoft/deberta-v3-xsmall", MODELS_CACHE / "deberta-v3-xsmall"),
    ]
    for repo_id, dest_dir in targets:
        has_weights = dest_dir.exists() and (
            (dest_dir / "model.safetensors").exists() or (dest_dir / "pytorch_model.bin").exists()
        )
        if has_weights:
            print(f"[preload] Already cached: {dest_dir}")
            continue
        print(f"[preload] Downloading {repo_id} -> {dest_dir}...")
        dest_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(repo_id=repo_id, local_dir=str(dest_dir))
        print(f"[preload] Cached {repo_id}")


def ensure_initial_sisa_shards():
    shard0_csv = ROOT_DIR / "sisa_adapters" / "partitions" / "shard_0.csv"
    shard0_pt = ROOT_DIR / "sisa_adapters" / "shard_0" / "adapter_model.pt"
    if shard0_csv.exists() and shard0_pt.exists():
        print("[preload] Initial SISA shard partitions and PyTorch adapters already present.")
        return
    if not (ROOT_DIR / "data" / "processed" / "train.csv").exists():
        print("[preload] train.csv absent; skipping initial SISA build.")
        return
    if shard0_pt.exists():
        print("[preload] Pre-trained SISA LoRA weights present; materializing partition CSVs from train.csv...")
        from app.unlearning.engine import unlearning_engine
        ok = unlearning_engine._materialize_partition_csvs(respect_purged=True)
        print(f"[preload] Partition CSVs materialized: {ok}")
        return
    print("[preload] Pre-building initial 5 SISA shards & embedding cache...")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from app.unlearning.engine import unlearning_engine

    res = unlearning_engine.initialize_shards_from_dataset(respect_purged=False)
    print(f"[preload] SISA shards built: {res.get('status')} ({res.get('total_samples', 0)} samples)")


if __name__ == "__main__":
    ensure_models_cached()
    ensure_initial_sisa_shards()
