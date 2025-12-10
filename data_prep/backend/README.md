# Data Preparation Backend

Separate backend for data preparation tasks, independent from the main Curious Mario application.

## Features

- Pinyin gap fill suggestions management
- English vocabulary suggestions
- Image extraction and management

## Setup

```bash
cd data_prep/backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

The API will be available at `http://localhost:8001`

