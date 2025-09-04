# Vibe Coding Agent System Manual

## Overview
Claude Code uses specialized agents to handle different types of development tasks. Each agent is optimized for specific domains and automatically selected based on task requirements.

## How Agent Selection Works

### Automatic Selection
Claude Code analyzes your request and automatically selects the most appropriate agent based on:
- **Keywords and context** in your request
- **File types** and project structure
- **Task complexity** and scope
- **Domain expertise** required

### Manual Selection
You can explicitly request specific agents by mentioning them in your request:
- "Use the backend-engineer agent to implement this API"
- "Have the ui-design-expert review this component"

## Available Agents

### 🔧 general-purpose
**Responsibilities:**
- Complex multi-step research tasks
- Code searching across large codebases
- General development tasks that don't fit other specializations
- Coordinating between multiple domains

**When to use:**
- Exploring unfamiliar codebases
- Multi-domain tasks requiring broad knowledge
- Initial project analysis and planning

**Example triggers:**
- "Search the entire codebase for authentication patterns"
- "Help me understand how this application works"

---

### 🎨 ui-design-expert
**Responsibilities:**
- Frontend component design and architecture
- User interface reviews and improvements
- CSS/styling optimization
- UX pattern recommendations
- Responsive design implementation

**When to use:**
- Creating or improving UI components
- Layout and styling decisions
- Frontend architecture planning
- Design system implementation

**Example triggers:**
- "Design a dashboard component for analytics"
- "Improve the user experience of this form"
- "Create a responsive navigation component"

---

### 🔌 backend-engineer
**Responsibilities:**
- API design and implementation
- Database schema and operations
- Server-side business logic
- Authentication and authorization systems
- Data modeling and validation
- Integration between frontend and backend

**When to use:**
- Building REST/GraphQL APIs
- Database design and migrations
- Authentication implementation
- Server-side functionality

**Example triggers:**
- "Create an API endpoint for user registration"
- "Design the database schema for this feature"
- "Implement JWT authentication"

---

### 📁 file-upload-api-handler
**Responsibilities:**
- File upload functionality implementation
- API integrations involving file transfers
- Data transfer scenarios
- Storage solutions (local, cloud)
- File validation and processing

**When to use:**
- Implementing file upload features
- Integrating with cloud storage APIs
- File processing workflows
- Data import/export functionality

**Example triggers:**
- "Add file upload to my React app"
- "Connect to AWS S3 for file storage"
- "Implement CSV import functionality"

---

### 🧪 tdd-test-engineer
**Responsibilities:**
- Test-driven development approach
- Test strategy design
- Testing framework setup
- Comprehensive test coverage
- Test automation

**When to use:**
- Before implementing new features (TDD approach)
- Creating test strategies
- Setting up testing infrastructure
- Improving test coverage

**Example triggers:**
- "Design tests for this authentication feature"
- "Set up testing framework for the project"
- "Create comprehensive test coverage"

---

### 📚 technical-writer
**Responsibilities:**
- API documentation
- README files and project documentation
- Code comments and inline documentation
- User guides and manuals
- Documentation maintenance

**When to use:**
- Creating or updating documentation
- After implementing new features
- Project setup and README creation
- API documentation updates

**Example triggers:**
- "Update the API documentation"
- "Create a user guide for this feature"
- "Write comprehensive project documentation"

---

### ⚙️ statusline-setup & output-style-setup
**Responsibilities:**
- Claude Code configuration
- Development environment setup
- Tool customization

**When to use:**
- Configuring Claude Code settings
- Customizing development workflow
- IDE integration setup

## Agent Collaboration

### Multi-Agent Workflows
Common patterns where multiple agents work together:

1. **Feature Development:**
   - `tdd-test-engineer` → Design tests
   - `backend-engineer` → Implement API
   - `ui-design-expert` → Create frontend
   - `technical-writer` → Document feature

2. **File Upload Feature:**
   - `file-upload-api-handler` → Core implementation
   - `backend-engineer` → Database integration
   - `ui-design-expert` → Upload interface
   - `tdd-test-engineer` → Test coverage

3. **Project Setup:**
   - `general-purpose` → Initial analysis
   - `backend-engineer` → Server setup
   - `ui-design-expert` → Frontend scaffold
   - `technical-writer` → Documentation

## Best Practices

### Leverage Proactive Agents
- **ui-design-expert** and **technical-writer** work proactively
- They automatically engage when relevant changes are made
- Trust their recommendations for better code quality

### Be Specific in Requests
- Mention the domain clearly: "database", "frontend", "API", "tests"
- Include relevant context about your tech stack
- Specify the outcome you want

### Sequential vs Parallel Work
```markdown
# Sequential (when tasks depend on each other)
1. Design database schema (backend-engineer)
2. Create API endpoints (backend-engineer)  
3. Build UI components (ui-design-expert)
4. Write tests (tdd-test-engineer)

# Parallel (when tasks are independent)
- Database setup (backend-engineer)
- UI design system (ui-design-expert)
- Test framework setup (tdd-test-engineer)
```

## Project-Specific Guidelines

### File Uploads & API Integration
Given this project's focus on file uploads and API calls:
- **Always** engage `file-upload-api-handler` for upload features
- Use `backend-engineer` for database persistence
- Employ `ui-design-expert` for upload interfaces

### Code Quality Rules
Following project rules (claude.md):
- Agents will enforce 300-line module limits
- `tdd-test-engineer` creates tests before production code
- All agents provide progress updates
- Documentation stays current via `technical-writer`

## Troubleshooting

### Agent Not Selected
If the wrong agent is chosen:
- Be more specific in your request
- Explicitly mention the agent you want
- Provide more context about the task domain

### Multiple Agents Needed
For complex tasks:
- Break down into smaller, domain-specific subtasks
- Let Claude Code coordinate multiple agents
- Review the multi-agent workflow patterns above

---

*This manual is maintained by the technical-writer agent and updated as the project evolves.*