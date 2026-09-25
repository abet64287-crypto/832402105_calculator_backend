import unittest
from decimal import Decimal

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


if __name__ == "__main__":
    unittest.main()
