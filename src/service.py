"""Validation and safe arithmetic expression evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Context, Decimal, DecimalException, localcontext


MAX_EXPRESSION_LENGTH = 500
MAX_PARENTHESES_DEPTH = 100
DECIMAL_CONTEXT = Context(prec=34, Emax=999999, Emin=-999999)


@dataclass(frozen=True)
class CalculationError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class ExpressionParser:
    """Recursive-descent parser for numbers, +, -, *, /, and parentheses."""

    def __init__(self, expression: str):
        self.expression = expression.translate(str.maketrans({"×": "*", "÷": "/", "−": "-"}))
        self.position = 0
        self.depth = 0

    def parse(self) -> Decimal:
        try:
            with localcontext(DECIMAL_CONTEXT):
                value = self._expression()
                self._skip_spaces()
                if self.position != len(self.expression):
                    raise self._syntax_error("Unexpected character")
                if not value.is_finite():
                    raise CalculationError("RESULT_OUT_OF_RANGE", "The result is outside the supported range.")
                return value
        except DecimalException as exc:
            raise CalculationError("RESULT_OUT_OF_RANGE", "The result is outside the supported range.") from exc

    def _expression(self) -> Decimal:
        value = self._term()
        while True:
            operator = self._take_operator("+-")
            if operator is None:
                return value
            right = self._term()
            value = value + right if operator == "+" else value - right

    def _term(self) -> Decimal:
        value = self._unary()
        while True:
            operator = self._take_operator("*/")
            if operator is None:
                return value
            right = self._unary()
            if operator == "/":
                if right == 0:
                    raise CalculationError("DIVISION_BY_ZERO", "Cannot divide by zero.")
                value /= right
            else:
                value *= right

    def _unary(self) -> Decimal:
        sign = 1
        while True:
            operator = self._take_operator("+-")
            if operator is None:
                break
            if operator == "-":
                sign = -sign
        value = self._primary()
        return -value if sign < 0 else value

    def _primary(self) -> Decimal:
        self._skip_spaces()
        if self._current() == "(":
            self.position += 1
            self.depth += 1
            if self.depth > MAX_PARENTHESES_DEPTH:
                raise CalculationError("INVALID_EXPRESSION", "Parentheses are nested too deeply.")
            try:
                value = self._expression()
                self._skip_spaces()
                if self._current() != ")":
                    raise self._syntax_error("Missing closing parenthesis")
                self.position += 1
                return value
            finally:
                self.depth -= 1
        return self._number()

    def _number(self) -> Decimal:
        self._skip_spaces()
        start = self.position
        digits = 0
        saw_dot = False
        while (character := self._current()) is not None:
            if character in "0123456789":
                digits += 1
            elif character == "." and not saw_dot:
                saw_dot = True
            else:
                break
            self.position += 1
        if digits == 0:
            raise self._syntax_error("Expected a number or opening parenthesis")
        return Decimal(self.expression[start:self.position])

    def _take_operator(self, operators: str) -> str | None:
        self._skip_spaces()
        character = self._current()
        if character is not None and character in operators:
            self.position += 1
            return character
        return None

    def _skip_spaces(self) -> None:
        while (character := self._current()) is not None and character.isspace():
            self.position += 1

    def _current(self) -> str | None:
        if self.position >= len(self.expression):
            return None
        return self.expression[self.position]

    def _syntax_error(self, reason: str) -> CalculationError:
        return CalculationError("INVALID_EXPRESSION", f"{reason} at position {self.position + 1}.")


def evaluate(expression: str) -> Decimal:
    if not isinstance(expression, str):
        raise CalculationError("INVALID_EXPRESSION", "Expression must be a string.")
    if not expression.strip():
        raise CalculationError("INVALID_EXPRESSION", "Expression cannot be empty.")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculationError("EXPRESSION_TOO_LONG", f"Expression cannot exceed {MAX_EXPRESSION_LENGTH} characters.")
    return ExpressionParser(expression).parse()


def decimal_to_json_number(value: Decimal) -> int | float:
    """Return a JSON number, rejecting values JSON cannot represent finitely."""
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise CalculationError("RESULT_OUT_OF_RANGE", "The result is outside the supported range.") from exc
    if not math.isfinite(number) or (number == 0 and value != 0):
        raise CalculationError("RESULT_OUT_OF_RANGE", "The result is outside the supported range.")
    if value == value.to_integral_value():
        return int(value)
    return number


def decimal_to_storage(value: Decimal) -> str:
    return format(value, "f")
