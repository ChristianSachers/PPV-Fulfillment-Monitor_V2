# Claude Code Project Configuration

This file contains project-specific information and commands for Claude Code.

## Project Overview
Web application with database persistence, file upload capabilities, and API integration.

## User Rules - MUST BE RESPECTED AT ALL TIMES!
- no modul or class is allowed to exceed 300 lines of code.
- any code change that would bring a modul or class over 300 lines of code needs to be explained to the user and a proposal for splitting must be created
- the first step of any change is to create a test case, no production code is allowed to be written without a test case upfront
- never assume anything. if you have questions, directly ask the User
- if the users asks for bigger tasks, propose a multi-step plan. each step must be small enough to be executable in less than 2 minutes
- always provide progress information when performing a task (e.g. 10% done, 20% done, ...)
- always keep the documentation up to date 

## Key Commands

### Development
```bash
# Frontend development server
npm run dev

# Backend development server  
npm run start:dev

# Database migrations
npm run db:migrate

# Run tests
npm test
```

### Build & Deploy
```bash
# Build frontend
npm run build

# Start production server
npm start

# Docker containers
docker-compose up -d
```

📁 Project Structure:
  ├── frontend/          # Client-side application
  │   ├── src/
  │   │   ├── components/   # Reusable UI components
  │   │   ├── pages/        # Route pages
  │   │   ├── hooks/        # Custom React hooks
  │   │   ├── services/     # API calls
  │   │   ├── utils/        # Helper functions
  │   │   ├── assets/       # Images, fonts, etc.
  │   │   └── styles/       # CSS/styling files
  │   └── public/           # Static assets
  │
  ├── backend/           # Server-side API
  │   ├── src/
  │   │   ├── routes/       # API endpoints
  │   │   ├── controllers/  # Request handlers
  │   │   ├── models/       # Database models
  │   │   ├── middleware/   # Auth, validation, etc.
  │   │   ├── services/     # Business logic
  │   │   ├── utils/        # Helper functions
  │   │   └── config/       # App configuration
  │   └── uploads/          # File upload storage
  │
  ├── database/          # Database management
  │   ├── migrations/       # Schema changes
  │   ├── seeds/           # Test data
  │   ├── schema/          # Database schema
  │   └── backups/         # Database backups
  │
  ├── shared/            # Common code
  │   ├── types/           # TypeScript types
  │   ├── constants/       # Shared constants
  │   └── utils/           # Shared utilities
  │
  ├── tests/             # Testing
  │   ├── unit/            # Unit tests
  │   ├── integration/     # Integration tests
  │   └── e2e/             # End-to-end tests
  │
  ├── uploads/           # Global upload storage
  ├── docs/              # Documentation
  └── [config files]     # .gitignore, docker-compose.yml, etc.

## Database
- Development: Local database via Docker
- Production: Configured via environment variables

## File Uploads
- Local development: `./uploads` and `./backend/uploads`
- Production: Cloud storage (S3, etc.)

## Environment Variables
Copy `.env.example` to `.env` and configure:
- Database credentials
- API keys
- File storage settings