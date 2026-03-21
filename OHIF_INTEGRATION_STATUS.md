# OHIF Viewer Integration Status

## ✅ Completed Steps

### 1. Django DICOMweb Backend
- **Created DICOMweb API endpoints** in `app/views.py`:
  - `dicomweb_studies` - QIDO-RS: Query for studies
  - `dicomweb_study_series` - QIDO-RS: Query series in a study
  - `dicomweb_series_instances` - QIDO-RS: Query instances in a series
  - `dicomweb_instance` - WADO-RS: Retrieve DICOM instances
  - `dicomweb_instance_frames` - WADO-RS: Retrieve image frames
  - `dicomweb_store` - STOW-RS: Store modified RT structures
  - `dicomweb_options` - Handle CORS preflight requests

- **Added URL routes** in `app/urls.py` for all DICOMweb endpoints

- **Configured CORS** in `spatialmetrics/settings.py`:
  - Added `corsheaders` to INSTALLED_APPS
  - Added CORS middleware
  - Configured CORS to allow localhost:3000 (OHIF)
  - Set up proper CORS headers for DICOMweb

### 2. OHIF Viewer Setup
- **Cloned OHIF Viewer** repository (latest version)
- **Installed dependencies** using yarn with `--ignore-engines` flag
- **Created custom configuration** at `ohif-viewer/platform/app/public/config/django-dicomweb.js`:
  - Points to Django DICOMweb server at `http://localhost:8000/dicomweb`
  - Configured for RT structure editing with STOW-RS support
  
- **Built OHIF for production** using `APP_CONFIG=config/django-dicomweb.js yarn run build`
  - Build output: `ohif-viewer/platform/app/dist/`
  - Build size: ~219 MB (includes all assets)

### 3. Django UI Integration
- **Added "Open in OHIF Viewer" button** to `study_detail.html`
- Created template for OHIF viewer page at `app/templates/app/ohif_viewer.html`

### 4. Dependencies Installed
- `pydicom` - DICOM file handling
- `pynetdicom` - DICOM networking
- `dicomweb-client` - DICOMweb client utilities
- `django-cors-headers` - CORS support

## 📋 Next Steps for Local Testing

### Step 1: Start Django Development Server
```bash
cd /mnt/share/spatial_overlap_metrics_app
source venv/bin/activate
python manage.py runserver
```

### Step 2: Start OHIF Viewer
In a new terminal:
```bash
cd /mnt/share/spatial_overlap_metrics_app/ohif-viewer/platform/app
npx serve ./dist -c ../public/serve.json -p 3000
```

Or use the development server:
```bash
cd /mnt/share/spatial_overlap_metrics_app/ohif-viewer
APP_CONFIG=config/django-dicomweb.js yarn run dev
```

### Step 3: Test the Integration
1. Open Django app: `http://localhost:8000`
2. Navigate to a study with DICOM data
3. Click "Open in OHIF Viewer" button
4. OHIF should open in a new tab and load the study from Django's DICOMweb endpoints

### Step 4: Test RT Structure Editing
1. Load a study with RT structures in OHIF
2. Use OHIF's segmentation tools to edit structures
3. Save the modified RT structure
4. Verify it's stored back to Django via STOW-RS endpoint

## 🐳 Docker Integration (Pending)

To integrate OHIF into docker-compose.yml, add this service:

```yaml
  ohif-viewer:
    build:
      context: ./ohif-viewer
      dockerfile: Dockerfile
    container_name: comet-ohif
    restart: unless-stopped
    ports:
      - "3000:80"
    environment:
      - APP_CONFIG=/usr/share/nginx/html/config/django-dicomweb.js
    depends_on:
      - comet-web
```

Update the OHIF config to use the Docker network:
- Change `http://localhost:8000` to `http://comet-web:8000` in the config

## 🔧 Configuration Files

### Django Settings (`spatialmetrics/settings.py`)
- CORS enabled for localhost:3000
- OHIF_VIEWER_URL setting added
- DICOMWEB_ROOT setting added

### OHIF Config (`ohif-viewer/platform/app/public/config/django-dicomweb.js`)
- Configured to use Django DICOMweb endpoints
- Supports RT structure editing
- STOW-RS enabled for saving modifications

## 📝 Important Notes

1. **DICOM Files**: Ensure your DICOM instances have valid `instance_file_path` in the database
2. **RT Structures**: The STOW-RS endpoint will create/update RT structure instances
3. **CORS**: CORS is configured to allow all origins in development - restrict in production
4. **Node Version**: OHIF requires Node.js 22.12.0+ (currently using 22.12.0)
5. **Build Time**: OHIF build takes ~90 seconds

## 🎯 Testing Checklist

- [ ] Django server starts successfully
- [ ] OHIF viewer serves on port 3000
- [ ] DICOMweb endpoints return study list
- [ ] OHIF loads study from Django
- [ ] Images display correctly in OHIF
- [ ] RT structures load in OHIF
- [ ] Can edit RT structures in OHIF
- [ ] Modified RT structures save back to Django
- [ ] Database updates with new RT structure data

## 🚀 Production Deployment

For production:
1. Build OHIF with production config
2. Serve OHIF static files via nginx
3. Update CORS settings to restrict origins
4. Use proper authentication for DICOMweb endpoints
5. Enable HTTPS for both Django and OHIF
