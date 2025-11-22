# Contributing to Phenomenological Evidence System

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Security](#security)

---

## Code of Conduct

### Our Commitment

This project is built with care for vulnerable people in pain. We are committed to:
- **Accessibility-first design** - Every feature must be usable by someone with brain fog
- **Privacy protection** - PHI handling must meet HIPAA standards
- **Transparency** - All cryptographic operations must be explainable
- **Respectful collaboration** - Kind, constructive feedback

### Expected Behavior

- Be respectful and inclusive
- Focus on what's best for the project and users
- Accept constructive criticism gracefully
- Prioritize user accessibility and privacy

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 12+ (or Docker)
- Git
- Basic understanding of FastAPI, SQLAlchemy, and cryptography

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/nft_the_conatus.git
cd nft_the_conatus
```

2. **Set up development environment**

```bash
# Install with development dependencies
make dev

# Create .env file
make env
# Edit .env with your settings

# Install pre-commit hooks
pre-commit install
```

3. **Start development environment**

```bash
# Option 1: Docker (recommended)
make docker-up
make migrate

# Option 2: Local PostgreSQL
# Create database: createdb phenomenological_evidence
make migrate
make run
```

4. **Verify setup**

```bash
make health-check
make test
```

---

## Development Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions/modifications

### Commit Messages

Use conventional commits format:

```
type(scope): brief description

Longer description if needed.

Fixes #issue_number
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(attestation): add chain verification endpoint

Implements GET /verify/:persona_id endpoint that validates
entire attestation chain integrity.

Fixes #42
```

```
fix(phi): prevent key rotation during active encryption

Added lock to prevent race condition during key rotation.

Fixes #127
```

### Making Changes

1. **Create a branch**
```bash
git checkout -b feature/amazing-feature
```

2. **Make your changes**
```bash
# Edit code
# Add tests
# Update documentation
```

3. **Run quality checks**
```bash
make format      # Format code
make lint        # Check linting
make type-check  # Type checking
make test        # Run tests
```

4. **Commit changes**
```bash
git add .
git commit -m "feat(scope): description"
```

5. **Push to your fork**
```bash
git push origin feature/amazing-feature
```

---

## Coding Standards

### Python Style

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Type hints**: Use type annotations
- **Docstrings**: Google-style docstrings

### Code Quality Rules

1. **Accessibility First**
   - SMS flows must be single-step
   - Error messages must be clear and actionable
   - No assumption of technical knowledge

2. **Security**
   - Never log PHI or encryption keys
   - Always use parameterized SQL queries
   - Validate all user input
   - Follow OWASP Top 10 guidelines

3. **Cryptography**
   - Document all crypto operations
   - Use established libraries (don't roll your own crypto)
   - Make operations explainable for legal purposes
   - Include Daubert considerations

4. **Database**
   - Use migrations for schema changes
   - Never bypass ORM for data modification
   - Maintain referential integrity

5. **Testing**
   - Unit tests for business logic
   - Integration tests for workflows
   - Mark crypto tests with `@pytest.mark.crypto`
   - Aim for >80% coverage

### Example Code

```python
from typing import Optional
from uuid import UUID


def create_attestation_entry(
    persona_token_id: UUID,
    payload: dict,
    previous_hash: Optional[str] = None,
) -> AttestedEntry:
    """
    Create a new attestation entry in the hash chain.

    Args:
        persona_token_id: The persona creating the attestation
        payload: The data to attest to
        previous_hash: Hash of previous entry (None for first entry)

    Returns:
        The created attestation entry

    Raises:
        ValueError: If payload is invalid
        IntegrityError: If chain is compromised

    Example:
        >>> entry = create_attestation_entry(
        ...     persona_token_id=uuid4(),
        ...     payload={"type": "pain", "value": 7},
        ... )
        >>> assert entry.entry_hash is not None
    """
    # Implementation...
```

---

## Testing

### Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# With coverage
make test-coverage

# Specific test file
pytest tests/test_attestation.py

# Specific test
pytest tests/test_attestation.py::test_chain_integrity
```

### Writing Tests

1. **Use appropriate markers**
```python
@pytest.mark.unit
@pytest.mark.crypto
def test_sign_entry(signing_service):
    """Test signing an attestation entry."""
    # Test implementation
```

2. **Use fixtures**
```python
def test_create_party(db_session, sample_party):
    """Test party creation."""
    assert sample_party.id is not None
```

3. **Test edge cases**
```python
def test_invalid_pain_value():
    """Test that invalid pain values are rejected."""
    with pytest.raises(ValueError):
        PainState(value=15.0)  # Max is 10.0
```

### Test Coverage

- Aim for >80% overall coverage
- 100% coverage for cryptographic functions
- 100% coverage for PHI handling
- Integration tests for all API endpoints

---

## Documentation

### Code Documentation

- **Module docstrings**: Explain purpose and architecture
- **Function docstrings**: Args, returns, raises, examples
- **Inline comments**: Explain "why", not "what"
- **Type hints**: All public functions

### User Documentation

When adding features, update:
- `README.md` - If adding major features
- `examples/` - Add usage examples
- `docs/` - Add detailed guides
- API docs - FastAPI auto-generates, but verify

### Accessibility Documentation

When changing user-facing features:
- Document in terms a non-technical person can understand
- Explain what happens and why
- Include examples with real scenarios
- Consider cognitive load

---

## Pull Request Process

### Before Submitting

- [ ] Code passes all tests (`make test`)
- [ ] Code is formatted (`make format`)
- [ ] Linting passes (`make lint`)
- [ ] Type checking passes (`make type-check`)
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)
- [ ] No merge conflicts with main

### PR Description Template

```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- List of specific changes
- What was added/modified/removed

## Testing
- How was this tested?
- What test cases were added?

## Accessibility Impact
- Does this affect user interactions?
- Is it still accessible to someone with brain fog?

## Security Impact
- Does this handle PHI?
- Any cryptographic changes?
- New dependencies?

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Code formatted
- [ ] Accessibility considered
- [ ] Security reviewed
```

### Review Process

1. **Automated checks** - CI runs tests, linting, type checking
2. **Code review** - Maintainers review for:
   - Code quality
   - Security implications
   - Accessibility impact
   - Test coverage
3. **Feedback** - Address comments and suggestions
4. **Approval** - Two approvals required for merge
5. **Merge** - Squash and merge to main

---

## Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead, email: security@conatus.project (or create a private security advisory)

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Guidelines

1. **PHI Handling**
   - Always encrypt PHI at rest
   - Use PHI separation pattern
   - Audit all PHI access

2. **Cryptography**
   - Use established libraries
   - Document key management
   - Explain operations for legal review

3. **Input Validation**
   - Validate all user input
   - Sanitize for SQL injection
   - Check for XSS in text fields

4. **Dependencies**
   - Keep dependencies updated
   - Run security audits (`make audit`)
   - Review new dependencies carefully

---

## Questions?

- **General questions**: Open a GitHub Discussion
- **Bug reports**: Open a GitHub Issue
- **Security issues**: Email security@conatus.project
- **Feature requests**: Open a GitHub Issue with `[Feature Request]` prefix

---

Thank you for contributing to a system built with care for those in pain! 💙
