# System uruchomienia - Blockchain + Torrent

## Struktura systemu

1. **Python Backend** (port 5001) - Blockchain
2. **Node.js Torrent API** (port 3000) - Torrenty
3. **Angular Frontend** (port 4200) - UI

## Instrukcja uruchomienia

### 1. Python Backend (Blockchain)

```powershell
cd backend
pip install -r requirements.txt
python app.py
```

Blockchain będzie dostępny na: http://localhost:5001

### 2. Node.js Torrent API

```powershell
cd node
npm install
# Uruchom za pomocą skryptu:
start-torrent-server.bat
# LUB bezpośrednio:
npm start
```

Torrent API będzie dostępne na: http://localhost:3000

### 3. Angular Frontend

```powershell
cd frontend
npm install
ng serve
```

Frontend będzie dostępny na: http://localhost:4200

## Funkcjonalności

### Frontend

- Upload obrazu do blockchain (przez Python backend)
- Wyświetlanie blockchain
- Przycisk "Create Torrent" - tworzy plik .torrent z danych blockchain
- Przycisk "Download .torrent" - pobiera plik .torrent

### API Endpoints

#### Python Backend (http://localhost:5001)

- `POST /blockchain/image/process` - upload obrazu
- `GET /blockchain/chain` - pobierz blockchain
- `GET /blockchain/image/data/:imageId` - pobierz dane obrazu dla torrent

#### Node.js Torrent API (http://localhost:3000)

- `POST /api/create-torrent/:imageId` - tworzy torrent z blockchain
- `GET /api/download/torrent/:filename` - pobiera plik .torrent
- `GET /api/seeding/status` - status seedowania
- `GET /api/health` - health check

## Workflow

1. User uploada obraz przez frontend
2. Obraz zostaje zapisany w blockchain (Python)
3. User klika "Create Torrent"
4. Node.js pobiera dane z Python blockchain
5. Tworzy plik .torrent i rozpoczyna seedowanie
6. User może pobrać plik .torrent

## Wymagania

- Python 3.9+
- Node.js 16+
- Angular CLI
- Zainstalowane zależności (npm install / pip install)
