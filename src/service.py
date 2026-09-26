"""Validation and safe arithmetic expression evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import (
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    ROUND_HALF_EVEN,
    Underflow,
    localcontext,
)


MAX_EXPRESSION_LENGTH = 500
MAX_PARENTHESES_DEPTH = 100
DECIMAL_CONTEXT = Context(prec=34, Emax=308, Emin=-324)
DECIMAL_CONTEXT.traps[Underflow] = True
TRIG_CONTEXT = Context(prec=70, Emax=308, Emin=-324)
MAX_TRIG_ARGUMENT = Decimal("1000000")
PI = Decimal(
    "3.14159265358979323846264338327950288419716939937510582097494459230781640628620899"
)
E = Decimal(
    "2.71828182845904523536028747135266249775724709369995957496696762772407663035354759"
)
FUNCTION_NAMES = frozenset({"sin", "cos", "tan", "sqrt", "ln", "log", "abs"})


@dataclass(frozen=True)
class CalculationError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class ExpressionParser:
    """Recursive-descent parser for arithmetic and selected scientific functions."""

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
        value = self._power()
        return -value if sign < 0 else value

    def _power(self) -> Decimal:
        base = self._primary()
        if self._take_operator("^") is None:
            return base
        self._enter_depth()
        try:
            # Parsing the right operand as unary makes ^ right associative and
            # allows 2^-3 while keeping -2^2 equal to -(2^2).
            exponent = self._unary()
        finally:
            self.depth -= 1
        if base == 0:
            if exponent == 0:
                raise CalculationError("DOMAIN_ERROR", "Zero to the power of zero is undefined.")
            if exponent < 0:
                raise CalculationError("DIVISION_BY_ZERO", "Cannot divide by zero.")
        if base < 0 and exponent != exponent.to_integral_value():
            raise CalculationError("DOMAIN_ERROR", "A negative base requires an integer exponent.")
        try:
            return base ** exponent
        except DivisionByZero as exc:
            raise CalculationError("DIVISION_BY_ZERO", "Cannot divide by zero.") from exc
        except InvalidOperation as exc:
            raise CalculationError("DOMAIN_ERROR", "The power is undefined for these values.") from exc

    def _primary(self) -> Decimal:
        self._skip_spaces()
        if self._current() == "(":
            self.position += 1
            return self._parenthesized()
        if self._current() == "π":
            self.position += 1
            return +PI
        if (character := self._current()) is not None and character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
            return self._identifier()
        return self._number()

    def _identifier(self) -> Decimal:
        start = self.position
        while (character := self._current()) is not None and character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.position += 1
        name = self.expression[start:self.position]
        if name == "pi":
            return +PI
        if name == "e":
            return +E
        if name not in FUNCTION_NAMES:
            raise self._syntax_error("Unknown identifier")
        self._skip_spaces()
        if self._current() != "(":
            raise self._syntax_error("Expected an opening parenthesis after the function name")
        self.position += 1
        argument = self._parenthesized()
        return self._function(name, argument)

    def _parenthesized(self) -> Decimal:
        self._enter_depth()
        try:
            value = self._expression()
            self._skip_spaces()
            if self._current() != ")":
                raise self._syntax_error("Missing closing parenthesis")
            self.position += 1
            return value
        finally:
            self.depth -= 1

    def _enter_depth(self) -> None:
        self.depth += 1
        if self.depth > MAX_PARENTHESES_DEPTH:
            self.depth -= 1
            raise CalculationError("INVALID_EXPRESSION", "Expression is nested too deeply.")

    def _function(self, name: str, argument: Decimal) -> Decimal:
        if name == "abs":
            return abs(argument)
        if name == "sqrt":
            if argument < 0:
                raise CalculationError("DOMAIN_ERROR", "Square root requires a nonnegative number.")
            return argument.sqrt()
        if name in {"ln", "log"}:
            if argument <= 0:
                raise CalculationError("DOMAIN_ERROR", "Logarithm requires a positive number.")
            if name == "ln" and argument == +E:
                return Decimal(1)
            return argument.ln() if name == "ln" else argument.log10()
        return self._trigonometric(name, argument)

    @staticmethod
    def _trigonometric(name: str, argument: Decimal) -> Decimal:
        if abs(argument) > MAX_TRIG_ARGUMENT:
            raise CalculationError(
                "RESULT_OUT_OF_RANGE", "Trigonometric arguments cannot exceed 1000000 radians in magnitude."
            )
        with localcontext(TRIG_CONTEXT):
            half_pi = PI / 2
            two_pi = 2 * PI
            cycles = (argument / two_pi).to_integral_value(rounding=ROUND_HALF_EVEN)
            angle = argument - cycles * two_pi
            landmark = int((angle / half_pi).to_integral_value(rounding=ROUND_HALF_EVEN))
            difference = angle - landmark * half_pi
            tolerance = Decimal("1e-33") * max(Decimal(1), abs(argument))
            if abs(difference) <= tolerance and (landmark != 0 or cycles != 0 or argument == 0):
                quarter = landmark % 4
                if name == "sin":
                    return Decimal((0, 1, 0, -1)[quarter])
                if name == "cos":
                    return Decimal((1, 0, -1, 0)[quarter])
                if quarter % 2:
                    raise CalculationError("DOMAIN_ERROR", "Tangent is undefined at this angle.")
                return Decimal(0)
            if name == "tan":
                quarter_pi = PI / 4
                quarter_landmark = int((angle / quarter_pi).to_integral_value(rounding=ROUND_HALF_EVEN))
                if abs(angle - quarter_landmark * quarter_pi) <= tolerance:
                    quarter = quarter_landmark % 4
                    if quarter == 1:
                        return Decimal(1)
                    if quarter == 3:
                        return Decimal(-1)

            sine = ExpressionParser._series_sine(angle)
            cosine = ExpressionParser._series_cosine(angle)
            if name == "sin":
                result = sine
            elif name == "cos":
                result = cosine
            else:
                result = sine / cosine
        with localcontext(DECIMAL_CONTEXT):
            return +result

    @staticmethod
    def _series_sine(angle: Decimal) -> Decimal:
        term = angle
        total = term
        for index in range(1, 120):
            term = -term * angle * angle / ((2 * index) * (2 * index + 1))
            updated = total + term
            if updated == total:
                return total
            total = updated
        return total

    @staticmethod
    def _series_cosine(angle: Decimal) -> Decimal:
        term = Decimal(1)
        total = term
        for index in range(1, 120):
            term = -term * angle * angle / ((2 * index - 1) * (2 * index))
            updated = total + term
            if updated == total:
                return total
            total = updated
        return total

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
