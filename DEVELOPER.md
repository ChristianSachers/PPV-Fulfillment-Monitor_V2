# Developer Documentation

Technical documentation for developers working on the PPV Fulfillment Monitor application.

## Prerequisites

- **Node.js** (18+ recommended)
- **Python 3.11+**
- **PostgreSQL 15** (installed via Homebrew)
- **npm** or **yarn**

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd PPV-Fulfillment-Monitor_V2

# Install frontend dependencies
cd frontend
npm install
cd ..

# Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..
```

## Development Server Options

### Option 1: Start Everything (Recommended)

```bash
# Start both frontend and backend servers
./start-dev.sh
```

This will:
- Start PostgreSQL (if not running)
- Start FastAPI backend on port 8001
- Start React frontend on port 3000
- Enable hot reload for development

### Option 2: Start Services Individually

```bash
# Backend only (FastAPI on port 8001)
cd backend
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend only (React TypeScript on port 3000)
cd frontend
npm run dev

# Database only (PostgreSQL)
brew services start postgresql@15
```

## Stopping the Application

### Stop Everything

```bash
# Stop all development servers
./stop-dev.sh
```

### Stop Individual Services

```bash
# Stop with Ctrl+C in terminal
# Or kill specific processes:
lsof -ti:8001 | xargs kill -9  # Stop backend
pkill -f "vite"                # Stop frontend
```

## Service URLs

Once started, access these URLs:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend App** | http://localhost:3000 | Main web application |
| **Backend API** | http://localhost:8001 | REST API endpoints |
| **API Documentation** | http://localhost:8001/docs | Interactive Swagger docs |
| **Database** | localhost:5432 | PostgreSQL database |

## Testing

```bash
# Run all tests
npm test

# Backend tests only
cd backend
python -m pytest

# Frontend tests only
cd frontend
npm test
```

## Database Operations

```bash
# Connect to database
psql -d ppv_fulfillment_dev

# Backup database
pg_dump ppv_fulfillment_dev > backup.sql

# Restore database
psql -d ppv_fulfillment_dev < backup.sql
```

## Build & Deploy

```bash
# Build frontend for production
cd frontend
npm run build

# Start production server
cd backend
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8001
```

## Project Structure

```
PPV-Fulfillment-Monitor_V2/
├── backend/                # FastAPI backend
│   ├── src/
│   │   ├── routes/        # API endpoints
│   │   ├── models/        # Database models
│   │   ├── services/      # Business logic
│   │   └── utils/         # Helper functions
│   └── tests/             # Backend tests
├── frontend/              # React TypeScript frontend
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Route pages
│   │   ├── services/      # API clients
│   │   └── hooks/         # Custom React hooks
│   └── public/            # Static assets
├── docs/                  # Documentation
└── uploads/               # File upload storage
```

## Configuration

Environment variables (create `.env` file):

```bash
# Database
DATABASE_URL=postgresql://localhost:5432/ppv_fulfillment_dev

# API Configuration
API_HOST=localhost
API_PORT=8001

# File Upload
MAX_FILE_SIZE=500MB
ALLOWED_EXTENSIONS=csv,xlsx,xls,json
```

## Development Guidelines

- **Code Style**: Follow project conventions (see `CLAUDE.md`)
- **Line Limit**: Keep modules under 300 lines
- **Testing**: Write tests before implementation (TDD)
- **Commits**: Use bulletpoint-style commit messages

## Contributing

1. Create feature branch from `master`
2. Follow TDD approach (tests first)
3. Keep changes focused and small
4. Update documentation as needed
5. Submit PR with clear description

## Detailed Troubleshooting

### Common Development Issues

**PostgreSQL not starting:**
```bash
brew services restart postgresql@15
```

**Port already in use:**
```bash
# Find and kill process using port
lsof -ti:8001 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

**Frontend build errors:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**Backend import errors:**
```bash
cd backend
pip install -r requirements.txt --upgrade
```

**Database connection issues:**
```bash
# Check if PostgreSQL is running
brew services list | grep postgresql

# Reset database if needed
dropdb ppv_fulfillment_dev
createdb ppv_fulfillment_dev
```

**File upload not working in development:**
```bash
# Ensure upload directories exist
mkdir -p uploads
mkdir -p backend/uploads
```

### Performance Issues

**Slow API responses:**
- Check database query performance
- Review N+1 query issues
- Monitor database connections

**Frontend build taking too long:**
```bash
# Clear build cache
cd frontend
rm -rf .vite
npm run build
```

## API Development

### Adding New Endpoints

1. Create route in `backend/src/routes/`
2. Add corresponding model in `backend/src/models/`
3. Implement business logic in `backend/src/services/`
4. Write tests in `backend/tests/`

### Frontend Integration

1. Add API client in `frontend/src/services/`
2. Create custom hook if needed in `frontend/src/hooks/`
3. Update components to use new endpoints
4. Add error handling and loading states

---

**For basic usage instructions, see the main [README.md](README.md) file.**