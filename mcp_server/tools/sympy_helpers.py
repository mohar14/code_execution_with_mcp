"""
Name: SymPy Helpers
Description: Utility functions for parsing, formatting, and converting SymPy expressions between different formats including LaTeX and string representations.
Version: 1.0.0
Dependencies: sympy>=1.12

This module provides expression manipulation utilities that complement the
symbolic-computation skill. Use these helpers when you need to convert
between expression formats or parse user input into symbolic form.

Available Functions:
- parse_expression: Parse a string into a SymPy expression
- to_latex: Convert a SymPy expression to LaTeX format
- from_latex: Parse LaTeX notation into a SymPy expression
- pretty_print_str: Get pretty-printed string representation
- expression_to_dict: Serialize expression to dictionary for JSON
"""

from sympy import Symbol, latex, sympify
from sympy.parsing.latex import parse_latex
from sympy.printing import pretty


def parse_expression(expr_string: str, symbol_names: str = "x y z"):
    """Parse a string into a SymPy expression with automatic symbol creation.

    Converts a mathematical expression string into a SymPy symbolic object.
    Symbols are automatically created based on the symbol_names parameter.

    Args:
        expr_string: Mathematical expression (e.g., "x**2 + 2*x + 1")
        symbol_names: Space-separated symbol names to use (default: "x y z")

    Returns:
        SymPy expression object

    Example:
        >>> expr = parse_expression("x**2 + 2*x + 1")
        >>> print(type(expr).__name__)
        Add

    Raises:
        SympifyError: If the expression cannot be parsed
    """
    local_symbols = {s: Symbol(s) for s in symbol_names.split()}
    return sympify(expr_string, locals=local_symbols)


def to_latex(expr, mode: str = "plain") -> str:
    """Convert a SymPy expression to LaTeX format.

    Renders a symbolic expression as a LaTeX string suitable for
    mathematical typesetting or display in markdown.

    Args:
        expr: SymPy expression to convert
        mode: Output mode - "plain" for raw LaTeX, "inline" for $...$,
              "display" for $$...$$

    Returns:
        LaTeX string representation

    Example:
        >>> from sympy import symbols, Integral
        >>> x = symbols('x')
        >>> expr = Integral(x**2, x)
        >>> print(to_latex(expr, mode="display"))
        $$\\int x^{2}\\, dx$$
    """
    latex_str = latex(expr)
    if mode == "inline":
        return f"${latex_str}$"
    elif mode == "display":
        return f"$${latex_str}$$"
    return latex_str


def from_latex(latex_string: str):
    """Parse a LaTeX mathematical expression into SymPy.

    Converts LaTeX notation (e.g., from a document or user input)
    into a SymPy expression for symbolic manipulation.

    Args:
        latex_string: LaTeX mathematical notation (e.g., "\\frac{x^2}{2}")

    Returns:
        SymPy expression object

    Example:
        >>> expr = from_latex(r"\\frac{x^2 + 1}{x - 1}")
        >>> print(expr)
        (x**2 + 1)/(x - 1)

    Note:
        Not all LaTeX constructs are supported. Complex expressions
        may require manual parsing.
    """
    return parse_latex(latex_string)


def pretty_print_str(expr, use_unicode: bool = True) -> str:
    """Get a pretty-printed string representation of an expression.

    Returns a human-readable string with proper mathematical formatting,
    suitable for console output or text-based display.

    Args:
        expr: SymPy expression to format
        use_unicode: Use Unicode symbols for better display (default: True)

    Returns:
        Pretty-printed string representation

    Example:
        >>> from sympy import sqrt, symbols
        >>> x = symbols('x')
        >>> print(pretty_print_str(sqrt(x)))
        sqrt(x)
    """
    return pretty(expr, use_unicode=use_unicode)


def expression_to_dict(expr) -> dict:
    """Serialize a SymPy expression to a dictionary for JSON compatibility.

    Converts an expression into a dictionary containing its string
    representation, LaTeX form, and type information.

    Args:
        expr: SymPy expression to serialize

    Returns:
        Dictionary with keys: 'string', 'latex', 'type', 'is_number'

    Example:
        >>> from sympy import sqrt
        >>> result = expression_to_dict(sqrt(2))
        >>> print(result['type'])
        Pow
    """
    return {
        "string": str(expr),
        "latex": latex(expr),
        "type": type(expr).__name__,
        "is_number": expr.is_number if hasattr(expr, "is_number") else False,
    }
