from datetime import datetime

def calculate_salary_deduction(
    employee_salary: float | int | None,
    leave_start: str,
    leave_end: str,
    leave_decision: str
) -> float:
    """
    Deterministic salary deduction calculator.
    Returns a NUMBER only.
    """

    # Only rejected leaves cause deduction
    if leave_decision.lower() != "rejected":
        return 0.0

    # Parse dates
    start_date = datetime.strptime(leave_start, "%Y-%m-%d").date()
    end_date = datetime.strptime(leave_end, "%Y-%m-%d").date()

    # Inclusive day count
    leave_days = (end_date - start_date).days + 1
    if leave_days <= 0:
        return 0.0

    # Salary calculation
    normalized_salary = float(employee_salary or 0)
    if normalized_salary <= 0:
        return 0.0

    daily_salary = normalized_salary / 30
    deduction = daily_salary * leave_days

    # Rounded for payroll safety
    return round(deduction, 2)
