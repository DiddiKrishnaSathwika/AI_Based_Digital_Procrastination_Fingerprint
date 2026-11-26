# ProcrastiSense AI

### AI-Based Digital Procrastination Fingerprint

**Understand your digital behavior. Identify distraction patterns. Build better focus habits.**

---

## 1. Overview

ProcrastiSense AI is a digital productivity monitoring and behavioral analysis application designed to help users understand their focus patterns and identify digital distractions.

Instead of simply measuring screen time, the system analyzes application activity and behavioral patterns to generate a personalized Digital Procrastination Fingerprint.

The fingerprint helps users understand their focus duration, distraction frequency, application usage patterns, and productivity behavior.

The project combines a web-based dashboard, a Flask backend, activity tracking, behavioral analytics, and personalized productivity insights.

## 2. Problem Statement

Traditional productivity applications primarily focus on screen time and application usage.

However, screen time alone does not explain why users lose concentration, which applications interrupt their work, or when they are most likely to become distracted.

Users need a system that helps them understand their individual digital behavior and recognize recurring procrastination patterns.

## 3. Proposed Solution

ProcrastiSense AI provides a personalized productivity monitoring system that analyzes digital activity and presents meaningful behavioral insights.

The system aims to:

- Monitor application activity and focus behavior.
- Identify frequently used and distracting applications.
- Analyze focus duration and application switching patterns.
- Generate a personalized Digital Procrastination Fingerprint.
- Estimate potential distraction risk.
- Provide productivity recommendations and interventions.
- Present activity history and analytics through an interactive dashboard.

## 4. Key Features

### User Authentication
- User registration and login.
- Authentication-related functionality.
- User-specific activity and productivity information.
- Password recovery and reset functionality.

### Activity Monitoring
- Windows desktop activity collection through the activity collector.
- Application and activity categorization.
- Recording activity information with timestamps.
- Tracking application usage and focus behavior.

### Digital Procrastination Fingerprint
- Personalized behavioral insights.
- Focus duration analysis.
- Distraction pattern identification.
- Application usage analysis.
- Identification of recurring productivity patterns.

### Distraction Risk Prediction
- Estimates potential distraction risk using the implemented prediction logic.
- Presents prediction results through the dashboard.
- Supports future integration of trained machine learning models.

### Personalized Interventions
- Productivity recommendations based on available behavioral information.
- Suggestions intended to help users recover focus and reduce distractions.

### Analytics Dashboard
- Interactive productivity dashboard.
- Activity timeline and historical records.
- Behavioral analytics and visualizations.
- Productivity summaries and reports.

## 5. Technology Stack

| Component | Technologies |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Data Visualization | Chart.js |
| Backend | Python, Flask |
| Database | Neon PostgreSQL |
| Activity Monitoring | Python, Windows activity collector |
| API Communication | REST API, JSON |
| Testing | Pytest |
| Development Environment | Visual Studio Code |

## 6. System Architecture

The application follows a frontend-backend architecture.

```text
       User
        |
        v
  Web Application
  HTML, CSS, JavaScript
        |
        | REST API / JSON
        v
    Flask Backend
        |
        +------------------+
        |                  |
        v                  v
   Neon PostgreSQL    Activity Collector
                           |
                           v
                   Windows Application
                     Activity Data
```

The frontend communicates with the Flask backend through API requests.

The backend processes application data, manages database operations, and provides information required by the dashboard and analytics components.

The Windows activity collector is a separate component responsible for collecting desktop activity information.

## 7. Project Structure

```text
ProcrastiSense-AI/
|
|-- backend/
|   |-- app.py
|   |-- activity_collector.py
|   |-- requirements.txt
|   |-- requirements-collector.txt
|   |-- requirements-dev.txt
|   |-- tests/
|   |-- scripts/
|   |-- pytest.ini
|   |
|   |-- procrastisense.db
|
|-- frontend/
|   |-- index.html
|   |-- app.js
|   |-- styles.css
|   |-- reset-password.html
|   |-- package.json
|
|-- scripts/
|
|-- README.md
|-- pyproject.toml
|-- requirements.txt
|-- vercel.json
```

*Note: Generated databases, virtual environments, caches, and local configuration files are environment-specific and should not be included in the public repository.*

The existing ignored `backend/procrastisense.db` SQLite file is not accessed,
changed, or automatically imported by the PostgreSQL backend. Keep a backup
and complete a separately verified one-time data import before relying on old
SQLite records in Neon.

## 8. Installation and Setup

### Prerequisites

- Python 3.x
- Visual Studio Code
- Git
- Windows operating system for the desktop activity collector

### Step 1: Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

```bash
cd ProcrastiSense-AI
```

### Step 2: Configure the Database

Create a root-level `.env` file (it is ignored by Git) with the Neon
`DATABASE_URL`, a locally generated `SECRET_KEY`, and the values required by
the email service. Do not commit credentials.

The backend loads this root `.env` for local development. Vercel deployments
must set those values in the project's Environment Variables instead.

### Step 3: Create a Virtual Environment

Run these commands from the repository root:

```powershell
python -m venv .venv
```

### Step 4: Activate the Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 5: Install Dependencies

```powershell
pip install -r backend\requirements.txt
```

### Step 6: Start the Backend

```powershell
python backend\app.py
```

### Step 7: Open the Application

Open the local application URL configured by the Flask backend in your browser.

For local development, the application uses port 5050.

```text
http://localhost:5050
```

### Running the tests

The backend tests create and drop a uniquely named PostgreSQL schema for each
test. The configured database user must be allowed to create schemas. Run from
the repository root:

```powershell
pip install -r backend\requirements-dev.txt
python -m pytest backend\tests
```

### Vercel deployment

Keep the Vercel project root set to the repository root so both `backend` and
`frontend` are part of the deployment. The root `pyproject.toml` points Vercel
to `backend.wsgi:app`; the root `requirements.txt` includes the backend runtime
dependencies, and `vercel.json` packages the sibling `frontend` files with the
function.

Set `DATABASE_URL`, `SECRET_KEY`, `APP_BASE_URL`, `EMAIL_API_URL`,
`EMAIL_API_TOKEN`, and `FLASK_ENV=production` as Vercel environment variables.
Set `FRONTEND_ORIGIN` if the frontend uses a separate origin; same-origin
frontend/API hosting does not require CORS. Use `.env.example` as the local
configuration template, replacing all placeholders privately.

For the desktop collector, install `backend\requirements-collector.txt` and
set `COLLECTOR_API_URL` to the deployed Flask API's `/api/activity` URL.
`FRONTEND_ORIGIN` must include the website origin for its local collector
bridge requests. The collector defaults to `http://localhost:5050/api/activity`
when no API URL is configured.

Vercel dashboard steps:

1. Import the repository and keep the project root at the repository root.
2. Add the environment variables above in Project Settings → Environment
   Variables for each deployment environment.
3. Use a Neon pooled `DATABASE_URL`; do not put credentials in the repository.
4. Deploy manually after reviewing the deployment configuration. No deployment
   is triggered by this repository configuration.

## 9. Activity Collector

ProcrastiSense AI includes a separate Windows activity collector.

The collector is designed to gather desktop application activity and communicate with the backend.

Its execution and configuration are separate from the main web application.

The collector requires its corresponding Python dependencies and appropriate backend connection settings.

## 10. Testing

The project includes tests for authentication, activity, analytics, collector
behavior, interventions, weekly reports, and integration functionality. See
the PostgreSQL test instructions in Section 8. Tests require a configured
`DATABASE_URL` and create isolated PostgreSQL schemas.

## 11. Privacy and Security

Privacy is an important consideration in the development of ProcrastiSense AI.

The system is designed around application-level activity monitoring rather than collecting the contents of private communications.

Security considerations include:

- User authentication.
- User-specific activity records.
- Controlled access to application data.
- Secure handling of configuration and credentials.
- Avoiding the collection of passwords and private message contents.

Users should be informed about activity monitoring and provide appropriate consent before using the collector.

## 12. Current Development Status

ProcrastiSense AI is an evolving software project.

The current codebase includes the web application, Flask backend, database integration, authentication-related functionality, activity collection components, analytics, and automated tests.

Further development focuses on improving behavioral analysis, prediction capabilities, personalization, testing, and deployment.

Machine learning capabilities should be considered implemented only when the corresponding models have been trained, evaluated, and integrated into the application.

## 13. Limitations and Future Enhancements

Potential future improvements include:

- Training and evaluating machine learning models for distraction prediction.
- Improving temporal behavioral analysis.
- Enhancing personalized productivity recommendations.
- Expanding application activity classification.
- Improving real-time monitoring.
- Strengthening privacy and security mechanisms.
- Deploying the application using production-ready infrastructure.
- Improving scalability and database management.

## 14. Disclaimer

ProcrastiSense AI is an academic software project developed for productivity monitoring and behavioral analysis.

Prediction outputs and behavioral insights should be interpreted according to the actual implementation and its limitations. They should not be considered guaranteed predictions of user behavior.

## 15. Project Information

**Project Name:** ProcrastiSense AI

**Project Title:** AI-Based Digital Procrastination Fingerprint

**Domain:** Artificial Intelligence and Machine Learning

**Project Type:** Academic Software Project

**Institution:** SR University

---

*ProcrastiSense AI — Understand your digital behavior and work towards better focus.*
