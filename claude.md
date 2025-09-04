# Claude Code Project Configuration

This file contains project-specific information and commands for Claude Code.

## Project Overview
Web application with database persistence, file upload capabilities, and API integration.

## User Rules - MUST BE RESPECTED AT ALL TIMES!
- the first step of any change is to create a test case, no production code is allowed to be written without a test case upfront
- never assume anything. if you have questions, directly ask the User
- if the users asks for bigger tasks, propose a multi-step plan. each step must be small enough to be executable in less than 2 minutes
- always provide progress information when performing a task (e.g. 10% done, 20% done, ...)
- always keep the documentation up to date
- always use the appropriate agent for each task
- commit messages must be short, bulletpoint style and descriptive
- use the challenging-mentor output style

### File Organization & Component Design - MUST BE RESPECTED AT ALL TIMES
  - **Cohesion Over Size**: Keep related functionality together. A 400-line component handling one user workflow is better than 4 artificially split 100-line components
  - **Single Responsibility**: Each file should have one clear, well-defined purpose that can be explained in one sentence
  - **Extract for Reusability**: If logic could be reused elsewhere, extract it to custom hooks, utilities, or services
  - **UI Component Guidelines**:
    - React components up to 500 lines are acceptable if handling a single user workflow
    - Extract state management to custom hooks when logic exceeds 150 lines
    - Split only when handling multiple unrelated features
  - **Service/Utility Guidelines**:
    - Keep focused utilities under 200 lines
    - Split when handling multiple unrelated domains
    - Configuration and type files have no size limits

  ### Code Quality Indicators
  - **Readability Test**: Can the file's purpose be understood within 30 seconds of opening it?
  - **Testability**: Can the component/function be tested effectively with clear, focused test cases?
  - **Naming Clarity**: Functions, variables, and components should have descriptive names that explain their purpose
  - **TypeScript Usage**: All interfaces, props, and function signatures must be properly typed

  ### When to Split Components
  - **Multiple User Workflows**: Component handles distinct, unrelated user tasks
  - **Mixed Concerns**: Component handles both UI rendering and business logic that could be extracted
  - **Repeated Patterns**: When similar logic appears in multiple places, extract to shared utilities
  - **Testing Complexity**: When tests become unwieldy due to component doing too many things

  ### AI Agent Optimization
  - **Clear Function Boundaries**: Use descriptive function names and proper separation
  - **Comprehensive TypeScript**: Type everything to help AI understand intent and interfaces
  - **Meaningful Comments**: Explain complex business logic, not obvious code
  - **Consistent Patterns**: Follow established patterns within the codebase for predictability

  ### Refactoring Triggers
  - **Explain Before Enforcing**: Before suggesting splits, explain why the current structure might be improved
  - **Quality Over Metrics**: Focus on improving maintainability, testability, and readability
  - **Context Matters**: Consider the domain complexity - financial calculations, UI workflows, and data processing naturally require larger components
  - **User Value**: Prioritize changes that improve user experience or developer productivity

  ### Testing Requirements
  - **Test-Driven Development**: Write tests before implementing new features
  - **Component Testing**: Test user interactions and state changes, not implementation details
  - **Integration Testing**: Verify API communication and data flow between components
  - **Accessibility Testing**: Ensure keyboard navigation and screen reader compatibility

## Key Commands

### Development
```bash
# Start both frontend and backend servers
./start-dev.sh

# Stop development servers
./stop-dev.sh
# Or use Ctrl+C to stop

# Backend only (FastAPI on port 8001)
cd backend && python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend only (React TypeScript on port 3001)
cd frontend && npm run dev

# Database operations (local PostgreSQL)
psql -d ppv_fulfillment_dev  # Connect to database
pg_dump ppv_fulfillment_dev > backup.sql  # Backup database
psql -d ppv_fulfillment_dev < backup.sql  # Restore database

# Run tests
npm test
```

### Build & Deploy
```bash
# Build frontend
cd frontend && npm run build

# Start production server
cd backend && python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8001
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
- Development: Local PostgreSQL 15 (installed via Homebrew)
- Database name: `ppv_fulfillment_dev`
- Connection: Local PostgreSQL server on default port 5432
- Production: Configured via environment variables

## File Uploads
- Local development: `./uploads` and `./backend/uploads`
- Production: Cloud storage (S3, etc.)

## Environment Variables
Copy `.env.example` to `.env` and configure:
- Database credentials
- API keys
- File storage settings