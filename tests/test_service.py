import unittest
from decimal import Decimal
from math import sin

from src.service import CalculationError, evaluate


class ExpressionParserTests(unittest.TestCase):
    def test_operator_precedence_parentheses_and_unary(self):
        cases = {
            "12+8": Decimal("20"),
            "1+2*3": Decimal("7"),
            "(1+2)*3": Decimal("9"),
            "10/2+7": Decimal("12"),
            "8-3*2": Decimal("2"),
            "-5+8": Decimal("3"),
            "3*-2": Decimal("-6"),
            "--5 + +2": Decimal("7"),
            "-(2+3)*4": Decimal("-20"),
            "3.5×2÷4": Decimal("1.75"),
            "  .5 + 2.  ": Decimal("2.5"),
            "0.1+0.2": Decimal("0.3"),
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(evaluate(expression), expected)

    def test_invalid_expressions_are_rejected(self):
        for expression in ["", " ", "1+", "2**3", "1//2", "2(3)", "(1+2", "()", "foo", "1e3", ".", "1..2", "1+2)"]:
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError) as context:
                    evaluate(expression)
                self.assertEqual(context.exception.code, "INVALID_EXPRESSION")

    def test_division_by_zero_and_length_limit(self):
        with self.assertRaises(CalculationError) as context:
            evaluate("5/(3-3)")
        self.assertEqual(context.exception.code, "DIVISION_BY_ZERO")

        with self.assertRaises(CalculationError) as context:
            evaluate("1" * 501)
        self.assertEqual(context.exception.code, "EXPRESSION_TOO_LONG")

    def test_scientific_functions_constants_and_nested_expressions(self):
        cases = {
            "2^3^2": Decimal("512"),
            "-2^2": Decimal("-4"),
            "(-2)^2": Decimal("4"),
            "2^-3": Decimal("0.125"),
            "2*3^2": Decimal("18"),
            "(2+1)^2": Decimal("9"),
            "sqrt(81)": Decimal("9"),
            "sqrt(abs(-9))": Decimal("3"),
            "abs(-4.5)": Decimal("4.5"),
            "ln(e)": Decimal("1"),
            "log(1000)": Decimal("3"),
            "sin(pi/2)": Decimal("1"),
            "sin(π)": Decimal("0"),
            "cos(pi)": Decimal("-1"),
            "tan(pi/4)": Decimal("1"),
            "sin(-pi/2)": Decimal("-1"),
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(evaluate(expression), expected)

    def test_trigonometric_values_use_radians(self):
        self.assertAlmostEqual(float(evaluate("sin(30)")), sin(30), places=14)
        self.assertAlmostEqual(float(evaluate("sin(pi/6)")), 0.5, places=14)
        self.assertAlmostEqual(float(evaluate("cos(pi/3)")), 0.5, places=14)
        self.assertAlmostEqual(float(evaluate("tan(pi/6)")), 1 / 3**0.5, places=14)

    def test_scientific_domain_and_range_errors(self):
        cases = {
            "sqrt(-1)": "DOMAIN_ERROR",
            "ln(0)": "DOMAIN_ERROR",
            "log(-10)": "DOMAIN_ERROR",
            "tan(pi/2)": "DOMAIN_ERROR",
            "tan(-pi/2)": "DOMAIN_ERROR",
            "0^0": "DOMAIN_ERROR",
            "(-2)^0.5": "DOMAIN_ERROR",
            "0^-1": "DIVISION_BY_ZERO",
            "10^1000": "RESULT_OUT_OF_RANGE",
            "sin(1000001)": "RESULT_OUT_OF_RANGE",
        }
        for expression, expected_code in cases.items():
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError) as context:
                    evaluate(expression)
                self.assertEqual(context.exception.code, expected_code)

    def test_scientific_syntax_is_restricted(self):
        for expression in ["sin 1", "sin()", "sqrt(4,5)", "pi(2)", "2pi", "log1", "foo(1)", "sin(pi", "2^^3"]:
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError) as context:
                    evaluate(expression)
                self.assertEqual(context.exception.code, "INVALID_EXPRESSION")


if __name__ == "__main__":
    unittest.main()
