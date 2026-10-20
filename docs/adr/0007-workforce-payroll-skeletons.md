# ADR 0007: Workforce and payroll skeletons

## Status

Accepted.

## Decision

The staff domain owns EmployeeProfile, Shift, AttendanceSession, and BreakSession. The payroll domain owns PayrollRun, Payslip, and PayslipLine.

Hard database invariants are enforced now: shifts and closed attendance/break intervals must end after they start, only one attendance session may remain open per employee, only one break may remain open per attendance session, payroll periods cannot end before they start, and a payroll run can contain only one payslip per employee.

Payroll amounts are Decimal-based and non-negative. PayslipLine supports earning and deduction categories without embedding Philippine contribution formulas in the schema.

## Deferred

- schedule-overlap prevention across separate shifts
- lateness and early-out calculations
- attendance correction requests
- leave workflows and balances
- payroll computation services
- SSS, PhilHealth, Pag-IBIG, withholding-tax formulas and current rates
- payroll finalization and payout workflows
