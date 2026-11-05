import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
"""Optional research upgrade: fine-tune DeBERTa-v3-base on the normalized train CSV.
Install requirements-optional-transformer.txt first.
This script is deliberately separate from the default lightweight SISA runtime.
"""
import argparse
import pandas as pd
import numpy as np
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer


def main(args):
    df = pd.read_csv(args.data).fillna('')
    df['label'] = df['label'].astype(int)
    ds = Dataset.from_pandas(df[['title','text','label']])
    tok = AutoTokenizer.from_pretrained(args.model_name)
    def tokenize(batch):
        joined=[f'{t} {x}'.strip() for t,x in zip(batch['title'], batch['text'])]
        return tok(joined, truncation=True, padding='max_length', max_length=args.max_length)
    ds=ds.map(tokenize, batched=True)
    ds=ds.remove_columns([c for c in ds.column_names if c not in {'input_ids','attention_mask','label'}])
    model=AutoModelForSequenceClassification.from_pretrained(args.model_name, num_labels=2)
    training_args=TrainingArguments(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        learning_rate=args.lr,
        logging_steps=20,
        save_strategy='epoch',
        report_to='none'
    )
    trainer=Trainer(model=model, args=training_args, train_dataset=ds, tokenizer=tok)
    trainer.train()
    trainer.save_model(args.output)
    tok.save_pretrained(args.output)
    print(f'Saved DeBERTa model to {args.output}')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data', default='data/processed/train.csv')
    p.add_argument('--model-name', default='microsoft/deberta-v3-base')
    p.add_argument('--output', default='artifacts/models/deberta-v3-base')
    p.add_argument('--epochs', type=int, default=2)
    p.add_argument('--batch', type=int, default=4)
    p.add_argument('--lr', type=float, default=2e-5)
    p.add_argument('--max-length', type=int, default=256)
    main(p.parse_args())
