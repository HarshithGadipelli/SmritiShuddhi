@echo off
setlocal
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  call .venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
if not exist .env copy .env.example .env
python scripts\generate_demo_dataset.py --rows 1200
python training\train_sisa.py --data data\processed\train.csv
python evaluation\evaluate_model.py
python app.py
