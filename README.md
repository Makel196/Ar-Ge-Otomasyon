# PDM Montaj Sihirbazı v2.0.0

Bu proje Electron (Frontend) ve Python (Backend) kullanılarak geliştirilmiştir.

## Kurulum

1. **Gereksinimler**:
   - Node.js (v16+)
   - Python (v3.8+)
   - SolidWorks ve PDM İstemcisi

2. **Backend Kurulumu**:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Frontend Kurulumu**:
   ```bash
   cd frontend
   npm install
   ```

## Çalıştırma

Uygulamayı geliştirmek ve çalıştırmak için:

```bash
cd frontend
npm run electron
```

Bu komut hem React geliştirme sunucusunu hem de Electron penceresini başlatacak, ayrıca arka planda Python sunucusunu çalıştıracaktır.

## Yapılandırma

- `config.json`: Uygulama ayarları.
- `backend/pdm_logic.py`: PDM ve SolidWorks otomasyon mantığı.
- `frontend/src`: Arayüz kodları.

## Notlar

- Uygulama çalışırken SolidWorks'ün açık olması önerilir, ancak kapalıysa otomatik açmaya çalışacaktır.
- PDM kasasına giriş yapılmış olmalıdır.
