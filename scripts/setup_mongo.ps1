$ErrorActionPreference='Stop'
docker compose up -d mongodb
Write-Host 'MongoDB is running on mongodb://localhost:27017'
Write-Host 'MongoDB Compass connection: mongodb://localhost:27017'
