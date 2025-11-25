# Skills Directory

This directory contains skills that can be used by AI agents to perform specialized tasks. Each skill provides domain-specific knowledge, instructions, and best practices.

## Skill Structure

Each skill is a directory containing a `Skill.md` file with the following structure:

```markdown
---
name: Skill Name
description: Short description of what this skill does (200 chars max)
version: 1.0.0
dependencies: package1>=1.0, package2>=2.0
---

# Skill Content

Detailed instructions, examples, and reference materials for the skill.
```

## Available Skills

### Symbolic Computation (`symbolic-computation`)

Enables AI agents to perform advanced symbolic mathematics using SymPy.

**Capabilities:**
- Symbolic algebra (simplification, expansion, factorization)
- Calculus (derivatives, integrals, limits)
- Equation solving and systems of equations
- Matrix operations and linear algebra
- Series expansions
- LaTeX rendering of mathematical expressions

**Dependencies:** `sympy>=1.12`

## Skills API

The MCP server exposes HTTP endpoints for retrieving skill information:

### List All Skills

```bash
GET /skills
```

**Response:**
```json
{
  "skills": [
    {
      "skill_id": "symbolic-computation",
      "name": "Symbolic Computation",
      "description": "Perform symbolic mathematics computations using SymPy...",
      "version": "1.0.0"
    }
  ],
  "count": 1
}
```

### Get Skill by Name

```bash
GET /skills/{skill_name}
```

**Example:**
```bash
curl http://localhost:8989/skills/symbolic-computation
```

**Response:**
```json
{
  "skill_id": "symbolic-computation",
  "name": "Symbolic Computation",
  "description": "Perform symbolic mathematics computations using SymPy...",
  "version": "1.0.0",
  "dependencies": "sympy>=1.12",
  "content": "# Symbolic Computation with SymPy\n\n..."
}
```

## Creating New Skills

To create a new skill:

1. Create a new directory with a descriptive name (e.g., `data-visualization`)
2. Create a `Skill.md` file with YAML frontmatter
3. Include clear instructions, examples, and best practices
4. Test the skill by retrieving it via the API

### Skill File Template

```markdown
---
name: Your Skill Name
description: What this skill does and when to use it
version: 1.0.0
dependencies: required-package>=1.0
---

# Your Skill Name

Brief introduction to the skill.

## When to Use This Skill

Invoke this skill when the user asks for:
- Specific use case 1
- Specific use case 2
- Specific use case 3

## Core Capabilities

### Feature 1

Description and code examples

\```python
# Example code
\```

### Feature 2

Description and code examples

## Best Practices

1. Practice 1
2. Practice 2

## Example Workflows

Demonstrate common usage patterns

## Tips for Agents

Guidance for AI agents using this skill
```

## Metadata Fields

### Required Fields

- **name**: Human-friendly name (64 characters max)
- **description**: Clear explanation of when to use this skill (200 characters max)

### Optional Fields

- **version**: Semantic version (e.g., 1.0.0)
- **dependencies**: Required packages in pip format

## Best Practices for Skills

1. **Keep each skill focused** on a single domain or workflow
2. **Write clear descriptions** that help agents understand when to invoke the skill
3. **Include concrete examples** showing input and expected output
4. **Document edge cases** and common pitfalls
5. **Version your skills** to track changes
6. **Test incrementally** after modifications
7. **Compose skills** - multiple focused skills work better than one monolithic skill

## Using Skills with Agents

Agents can retrieve skill information and use it to:

1. **Learn domain-specific best practices**
2. **Access reference implementations**
3. **Follow structured workflows**
4. **Understand when to apply specific techniques**

### Example: Agent Using Symbolic Computation Skill

```python
import httpx

# Retrieve the skill
response = httpx.get("http://localhost:8989/skills/symbolic-computation")
skill = response.json()

# Agent reads skill description to understand capabilities
print(skill["description"])

# Agent uses skill content as a reference
# to perform symbolic computation tasks
skill_instructions = skill["content"]

# Agent follows examples and best practices from the skill
# to correctly use SymPy for mathematical operations
```

## Security Considerations

- Never hardcode sensitive data (API keys, passwords) in skills
- Review third-party skills before enabling them
- Ensure skill dependencies are from trusted sources
- Use appropriate permissions when accessing external services
