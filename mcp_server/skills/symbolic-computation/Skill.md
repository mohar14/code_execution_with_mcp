---
name: Symbolic Computation
description: Perform symbolic mathematics computations using SymPy, including algebra, calculus, equation solving, and symbolic manipulations.
version: 1.0.0
dependencies: sympy>=1.12
---

# Symbolic Computation with SymPy

This skill enables you to perform advanced symbolic mathematics computations using the SymPy library. Use this skill when you need to work with mathematical expressions symbolically rather than numerically.

## When to Use This Skill

Invoke this skill when the user asks for:
- Symbolic algebra (simplification, expansion, factorization)
- Calculus operations (derivatives, integrals, limits)
- Solving equations and systems of equations
- Matrix operations and linear algebra
- Series expansions (Taylor, Laurent, Fourier)
- Mathematical expression manipulation
- Symbolic differentiation or integration
- LaTeX rendering of mathematical expressions

## Core Capabilities

### 1. Symbolic Variables and Expressions

```python
from sympy import symbols, expand, factor, simplify

# Define symbolic variables
x, y, z = symbols('x y z')

# Create and manipulate expressions
expr = (x + y)**2
expanded = expand(expr)  # x**2 + 2*x*y + y**2
factored = factor(expanded)  # (x + y)**2
simplified = simplify(expr)
```

### 2. Calculus Operations

```python
from sympy import diff, integrate, limit, oo

# Derivatives
f = x**3 + 2*x**2 + x
f_prime = diff(f, x)  # 3*x**2 + 4*x + 1
f_double_prime = diff(f, x, 2)  # 6*x + 4

# Integrals
integral = integrate(x**2, x)  # x**3/3
definite = integrate(x**2, (x, 0, 1))  # 1/3

# Limits
lim = limit(sin(x)/x, x, 0)  # 1
lim_inf = limit(1/x, x, oo)  # 0
```

### 3. Equation Solving

```python
from sympy import solve, Eq

# Solve equations
solutions = solve(x**2 - 4, x)  # [-2, 2]
solutions = solve(Eq(x**2 + 2*x + 1, 0), x)  # [-1]

# Systems of equations
from sympy import solve
system = [x + y - 2, x - y]
solutions = solve(system, [x, y])  # {x: 1, y: 1}
```

### 4. Series Expansions

```python
from sympy import series, sin, cos

# Taylor series
taylor = series(sin(x), x, 0, 10)
# x - x**3/6 + x**5/120 - x**7/5040 + x**9/362880 + O(x**10)
```

### 5. Matrix Operations

```python
from sympy import Matrix

# Create matrices
M = Matrix([[1, 2], [3, 4]])
N = Matrix([[5, 6], [7, 8]])

# Operations
M_inv = M.inv()  # Inverse
M_det = M.det()  # Determinant
M_eigen = M.eigenvals()  # Eigenvalues
```

### 6. LaTeX Rendering

```python
from sympy import latex

expr = x**2 + 2*x + 1
latex_str = latex(expr)  # 'x^{2} + 2 x + 1'
```

## Best Practices

1. **Always import what you need**: Import specific functions from sympy rather than using `from sympy import *`

2. **Define symbols clearly**: Use descriptive variable names and define all symbols at the start:
   ```python
   from sympy import symbols
   x, y, theta, t = symbols('x y theta t')
   ```

3. **Use rational numbers for exact results**:
   ```python
   from sympy import Rational
   result = Rational(1, 3) + Rational(1, 6)  # Exact: 1/2
   ```

4. **Simplify complex expressions**: Use `simplify()`, `expand()`, or `factor()` to make results more readable

5. **Handle assumptions**: Specify variable properties when needed:
   ```python
   x = symbols('x', real=True, positive=True)
   ```

## Common Usage Patterns

### Pattern 1: Differentiate and Evaluate
```python
from sympy import symbols, diff, lambdify
import numpy as np

x = symbols('x')
f = x**3 - 2*x**2 + x
f_prime = diff(f, x)

# Convert to numerical function
f_numeric = lambdify(x, f_prime, 'numpy')
values = f_numeric(np.array([1, 2, 3]))
```

### Pattern 2: Solve and Verify
```python
from sympy import symbols, solve, Eq

x = symbols('x')
equation = Eq(x**2 - 5*x + 6, 0)
solutions = solve(equation, x)

# Verify solutions
for sol in solutions:
    print(f"x = {sol}, check: {equation.subs(x, sol)}")
```

### Pattern 3: Symbolic to LaTeX
```python
from sympy import symbols, latex, integrate

x = symbols('x')
expr = integrate(x**2 * sin(x), x)
print(f"Result: {expr}")
print(f"LaTeX: {latex(expr)}")
```

## Error Handling

When working with SymPy, be aware of:
- **Undefined operations**: Some expressions may not have closed-form solutions
- **Timeout on complex computations**: Very complex symbolic operations may take time
- **Assumption conflicts**: Ensure variable assumptions are consistent

## Example Workflows

### Workflow 1: Complete Calculus Problem
```python
from sympy import symbols, diff, integrate, solve, pprint

# Define the problem
x = symbols('x')
f = x**3 - 3*x**2 + 2

# Find critical points
f_prime = diff(f, x)
critical_points = solve(f_prime, x)

# Check second derivative
f_double_prime = diff(f, x, 2)

# Evaluate at critical points
for point in critical_points:
    value = f.subs(x, point)
    concavity = f_double_prime.subs(x, point)
    print(f"At x={point}: f={value}, f''={concavity}")
```

### Workflow 2: Linear Algebra System
```python
from sympy import Matrix, symbols

# Define system of equations as matrix
A = Matrix([[2, 1], [1, 3]])
b = Matrix([5, 8])

# Solve Ax = b
x = A.inv() * b
print(f"Solution: {x}")

# Verify
print(f"Check: {A * x}")  # Should equal b
```

## Tips for Agents

1. Always use `pprint()` or `latex()` to format output for readability
2. When solving equations, check if solutions are real, complex, or symbolic
3. Use `evalf()` to get numerical approximations when needed
4. Combine with numerical libraries (NumPy, SciPy) for hybrid symbolic-numeric workflows
5. Check the SymPy documentation for advanced features: https://docs.sympy.org/

## Common Functions Reference

| Category | Functions |
|----------|-----------|
| Basic | `symbols`, `Symbol`, `simplify`, `expand`, `factor` |
| Calculus | `diff`, `integrate`, `limit`, `series` |
| Solving | `solve`, `solveset`, `dsolve` |
| Matrices | `Matrix`, `eye`, `zeros`, `ones` |
| Special | `sin`, `cos`, `exp`, `log`, `sqrt` |
| Output | `pprint`, `latex`, `preview` |

## Communication Guidelines

**Critical:** Always present any equations in your responses using a markdown-compatible LaTex syntax

## Related Helper Tools

This skill is complemented by the **sympy_helpers** tool module located at `/tools/sympy_helpers.py`. These utilities provide:

- **Expression parsing**: Convert strings and LaTeX to SymPy expressions
- **Format conversion**: Output expressions as LaTeX for display
- **Serialization**: Convert expressions to JSON-compatible dictionaries

### Using Helper Tools with This Skill

```python
# Import helpers
from sympy_helpers import parse_expression, to_latex, expression_to_dict

# Parse user input
expr = parse_expression("x**2 + 2*x + 1")

# Work with the expression using skill patterns
from sympy import diff, symbols
x = symbols('x')
derivative = diff(expr, x)

# Format output for display
print(to_latex(derivative, mode="display"))
# Output: $$2 x + 2$$
```
