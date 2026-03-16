
[![DOI](https://zenodo.org/badge/1175037586.svg)](https://doi.org/10.5281/zenodo.19044313)

# COMET - Contour Metrics

COMET (Contour Metrics) is an open source application designed to provide a graphical user interface for computation of spatial overlap metrics between structures delineated in radiotherapy. This application is built using Django and provides users with a web interface to:
1. Upload a set of DICOM files with images and structureset files. 
2. Automatically processes the DICOM data to extract information on the regions of interest in the structureset files.
3. Converts the dicom structureset regions of interest into compressed nifti files.
4. Computes STAPLE contours from a set of contours. 
5. Computes spatial overlap metrics between arbitrary pair of contours as well as between the STAPLE contour.
6. Allows users to download the metrics for further downstream analysis.
7. **Visualize NIfTI images and ROI overlays** using two methods:
   - **WebGL Viewer (niivue)**: GPU-accelerated, instant loading, interactive navigation
   - **Matplotlib Viewer**: Traditional static image generation


## Key Features

### Extract and Organize DICOM data
The system allows uses upload DICOM files in a zip archive. It will automatically extract and validate the DICOM files and save them in a structured fashion. 

### Extract ROI information from DICOM RTStructureSet Files

The system will also read all ROI contour information and store this information in the database. This allows us to match ROIs across structuresets for the same patient as well find groups of ROIs in multiple patients. 

### Convert DICOM to NIFTI

The system can automatically convert RT Image and associated structureset series into NIFTI files. In order to optimize space, these nifti files are stored in a compressed format. 

### Compute STAPLE contours

If a patient has more than one structureset available with the same ROI then a STAPLE contour can be computed for the ROI. This STAPLE contour will be saved as a nifti file and can be visualized as other ROIs.



### 📊 Spatial Overlap Metrics

COMET computes 12 spatial overlap metrics between binary contour pairs. All metrics are computed from NIfTI volumes with proper spacing consideration.

#### Available Metrics

1. **DSC (Dice Similarity Coefficient)**
   - Range: [0, 1], where 1 = perfect overlap
   - Formula: `DSC = 2|A ∩ B| / (|A| + |B|)`
   - Measures volumetric overlap between two structures

2. **Jaccard Similarity Coefficient**
   - Range: [0, 1], where 1 = perfect overlap
   - Formula: `Jaccard = |A ∩ B| / |A ∪ B|`
   - Alternative overlap metric, more sensitive to size differences than DSC

3. **HD95 (Hausdorff Distance 95th Percentile)**
   - Units: mm
   - Computes maximum surface distance per direction, then takes 95th percentile
   - Measures worst-case boundary disagreement (excluding outliers)
   - Lower values indicate better agreement

4. **MSD (Mean Surface Distance)**
   - Units: mm
   - Weighted average of mean distances from each surface to the other
   - Weighting based on number of surface points in each direction
   - Measures average boundary disagreement

5. **APL (Added Path Length)**
   - Units: mm
   - Slice-wise computation of contour length in reference missing from test
   - Uses 3mm distance threshold by default
   - Measures total missing contour length

6. **Surface DSC**
   - Range: [0, 1], where 1 = perfect surface agreement
   - Uses τ = 3mm tolerance by default
   - Measures surface overlap within acceptable deviation
   - Reference: Nikolov et al., J Med Internet Res 2021;23(7):e26151

7. **VOE (Volume Overlap Error)**
   - Range: [0, 1], where 0 = perfect overlap
   - Formula: `VOE = 1 - Jaccard`
   - Inverse of Jaccard coefficient

8. **VI (Variation of Information)**
   - Information-theoretic measure of segmentation disagreement
   - Based on mutual information between binary volumes
   - Lower values indicate better agreement

9. **Cosine Similarity**
   - Range: [-1, 1], where 1 = identical
   - Measures angular similarity between flattened volumes
   - Useful for overall shape comparison

10. **MDC (Mean Distance to Conformity)**
    - Units: mm
    - Average of OMDC and UMDC
    - Measures average distance from symmetric difference to nearest boundary

11. **OMDC (Overcontouring Mean Distance to Conformity)**
    - Units: mm
    - Mean distance from overcontoured voxels to reference boundary
    - Uses axis-aligned distance calculation

12. **UMDC (Undercontouring Mean Distance to Conformity)**
    - Units: mm
    - Mean distance from undercontoured voxels to test boundary
    - Uses axis-aligned distance calculation

#### Implementation Details

- **Surface Extraction**: Binary erosion method for efficient surface voxel identification
- **Distance Computation**: Euclidean distance transform for accurate distance measurements
- **Spacing Awareness**: All distance metrics account for voxel spacing (anisotropic support)
- **Edge Cases**: Handles empty volumes, single-voxel structures, and non-overlapping regions

#### Validation

Metrics have been validated against PlatiPy reference implementation:
- **Perfect Match**: DSC, Surface DSC, APL (0.0mm difference)
- **Minor Differences**: HD95 (~2.3mm), MSD (~1.2mm) due to different surface extraction methods
- See `compare_platipy_metrics.py` for QA validation script

#### References

- STAPLE: Warfield et al., IEEE TMI 2004
- Surface DSC: Nikolov et al., J Med Internet Res 2021
- Implementation: Based on draw-client-2.0 spatial overlap module

# Installation

## Quick Start with Docker Compose

The easiest way to run COMET is using Docker Compose with the pre-built image from AWS ECR Public.

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available for containers

### 1. Create Environment File

```bash
cp .env.docker .env
```

Edit `.env` with your settings:

```env
# Django Settings
DJANGO_SECRET_KEY=your-secure-secret-key-change-this
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database (PostgreSQL 17)
DJANGO_DB_NAME=comet_db
DJANGO_DB_USER=comet
DJANGO_DB_PASSWORD=your-secure-db-password

# RabbitMQ
RABBITMQ_DEFAULT_USER=comet
RABBITMQ_DEFAULT_PASS=your-secure-mq-password

# Celery (optional)
CELERY_WORKER_CONCURRENCY=4
```

### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  comet-db:
    image: postgres:17
    container_name: comet-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DJANGO_DB_NAME:-comet_db}
      POSTGRES_USER: ${DJANGO_DB_USER:-comet}
      POSTGRES_PASSWORD: ${DJANGO_DB_PASSWORD:-cometpassword}
    volumes:
      - comet_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DJANGO_DB_USER:-comet}"]
      interval: 5s
      timeout: 5s
      retries: 5

  comet-rabbitmq:
    image: rabbitmq:3.13-management-alpine
    container_name: comet-rabbitmq
    restart: unless-stopped
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_DEFAULT_USER:-comet}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_DEFAULT_PASS:-cometpassword}
    volumes:
      - comet_rabbitmq_data:/var/lib/rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"  # Management UI
    healthcheck:
      test: rabbitmq-diagnostics -q ping
      interval: 5s
      timeout: 5s
      retries: 5

  comet-web:
    image: public.ecr.aws/chavi/comet:latest
    container_name: comet-web
    restart: unless-stopped
    command: >
      sh -c "python manage.py migrate --noinput &&
             python manage.py collectstatic --noinput &&
             gunicorn spatialmetrics.wsgi:application --bind 0.0.0.0:8000 --workers 4"
    env_file:
      - .env
    environment:
      DJANGO_DB_HOST: comet-db
      DJANGO_CELERY_BROKER_URL: amqp://${RABBITMQ_DEFAULT_USER:-comet}:${RABBITMQ_DEFAULT_PASS:-cometpassword}@comet-rabbitmq:5672//
    volumes:
      - comet_media:/app/media
      - comet_static:/app/staticfiles
    ports:
      - "8000:8000"
    depends_on:
      comet-db:
        condition: service_healthy
      comet-rabbitmq:
        condition: service_healthy

  comet-celery:
    image: public.ecr.aws/chavi/comet:latest
    container_name: comet-celery
    restart: unless-stopped
    command: celery -A spatialmetrics worker -l info --concurrency 4
    env_file:
      - .env
    environment:
      DJANGO_DB_HOST: comet-db
      DJANGO_CELERY_BROKER_URL: amqp://${RABBITMQ_DEFAULT_USER:-comet}:${RABBITMQ_DEFAULT_PASS:-cometpassword}@comet-rabbitmq:5672//
    volumes:
      - comet_media:/app/media
    depends_on:
      comet-db:
        condition: service_healthy
      comet-rabbitmq:
        condition: service_healthy

volumes:
  comet_postgres_data:
  comet_rabbitmq_data:
  comet_media:
  comet_static:
```

### 3. Start the Application

```bash
docker-compose up -d
```

The application will be available at **http://localhost:8000**

### 4. RabbitMQ Management UI

Access the RabbitMQ management interface at **http://localhost:15672**

Default credentials from `.env`:
- Username: `comet`
- Password: (value of `RABBITMQ_DEFAULT_PASS`)

### 5. View Logs

```bash
# Web application logs
docker-compose logs -f comet-web

# Celery worker logs
docker-compose logs -f comet-celery

# All services
docker-compose logs -f
```

### 6. Stop the Application

```bash
docker-compose down
```

To remove all data (volumes):
```bash
docker-compose down -v
```

### Performance & Timeout Configuration

The Docker deployment is configured with the following settings:

| Service | Workers | Timeout | Description |
|---------|---------|---------|-------------|
| **Gunicorn (Web)** | 4 workers | 300s (5 min) | Handles HTTP requests including large DICOM uploads |
| **Celery (Tasks)** | 4 concurrent | N/A | Background processing for STAPLE, metrics computation |

**Why 5-minute timeout?**
- DICOM file uploads and conversions can take 30-120 seconds
- STAPLE computation triggers may need time to queue tasks
- The timeout prevents `504 Gateway Timeout` errors during long operations

**Note:** Heavy computations (STAPLE, spatial metrics) run in Celery workers, so the web server responds quickly. The extended timeout handles edge cases where synchronous processing occurs.

## Development Setup

To build locally instead of using the AWS image:

```bash
# Clone the repository
git clone <repository-url>
cd comet

# Copy and edit environment file
cp .env.docker .env

# Build and start with local Dockerfile
docker-compose -f docker-compose.yml up --build -d
```

 
# Standing on the Shoulders of Giants !

COMET would not be possible without the hard work of several people who have selflessly contributed open source code for the humankind. While the list of packages are available in the `requirements.txt` file, we would like to specifically acknowledge the following projects:

| Package | Citation | DOI/URL |
|---------|----------|---------|
| **Django** | Django Software Foundation. Django Web Framework. https://djangoproject.com | https://djangoproject.com |
| **Celery** | Ask Solem & contributors. Celery: Distributed Task Queue. https://docs.celeryq.dev | https://github.com/celery/celery |
| **RabbitMQ** | Pivotal Software, Inc. RabbitMQ: Message Broker. https://www.rabbitmq.com | https://www.rabbitmq.com |
| **PostgreSQL** | The PostgreSQL Global Development Group. PostgreSQL: The World's Most Advanced Open Source Relational Database. https://www.postgresql.org | https://www.postgresql.org |
| **SimpleITK** | Lowekamp BC, Chen DT, Ibáñez L, Blezek D. The Design of SimpleITK. Front. Neuroinform. 2013;7:45. | https://doi.org/10.3389/fninf.2013.00045 |
| **Platipy** | Chlap P, Finnegan RN. PlatiPy: Processing Library and Analysis Toolkit for Medical Imaging in Python. Journal of Open Source Software. 2023;8(86):5374. | https://doi.org/10.21105/joss.05374 |
| **scikit-image** | van der Walt S, Schönberger JL, Nunez-Iglesias J, et al. scikit-image: image processing in Python. PeerJ. 2014;2:e453. | https://doi.org/10.7717/peerj.453 |
| **SciPy** | Virtanen P, Gommers R, Oliphant TE, et al. SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. Nature Methods. 2020;17(3):261-272. | https://doi.org/10.1038/s41592-019-0686-2 |
| **NumPy** | Harris CR, Millman KJ, van der Walt SJ, et al. Array programming with NumPy. Nature. 2020;585(7825):357-362. | https://doi.org/10.1038/s41586-020-2649-2 |
| **pandas** | McKinney W. Data Structures for Statistical Computing in Python. Proceedings of the 9th Python in Science Conference. 2010:56-61. | https://doi.org/10.25080/Majora-92bf1922-00a |
| **Matplotlib** | Hunter JD. Matplotlib: A 2D Graphics Environment. Computing in Science & Engineering. 2007;9(3):90-95. | https://doi.org/10.1109/MCSE.2007.55 |
| **NiiVue** | NiiVue Contributors. NiiVue: WebGL2-based Medical Image Viewer. https://github.com/niivue/niivue | https://github.com/niivue/niivue |
