$ErrorActionPreference='Stop'
if (-not (Test-Path '.venv\Scripts\python.exe')) {
  py -3.11 -m venv .venv
  & .\.venv\Scripts\python.exe -m pip install --upgrade pip
  & .\.venv\Scripts\pip.exe install -r requirements.txt
}
if (-not (Test-Path '.env')) { Copy-Item .env.example .env }
if (-not (Test-Path 'data\processed\train.csv')) {
  & .\.venv\Scripts\python.exe scripts\generate_demo_dataset.py --rows 1200
}
if (-not (Test-Path 'artifacts\sisa\active_manifest.json')) {
  & .\.venv\Scripts\python.exe training\train_sisa.py --data data\processed\train.csv
}
Write-Host 'Starting Flask application at http://127.0.0.1:5000'
& .\.venv\Scripts\python.exe app.py
