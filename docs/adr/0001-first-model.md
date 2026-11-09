# ADR 1: My first model, and the baseline it must beat

**Status:** proposed
**Date:**

## Context
The model must classify each reading as Normal, Warning or Critical (R3). A missed Critical means no alert (R4); a false Critical is a false alarm (R9). Which mistake matters more for MedLink?

## Options considered
- A baseline with no learning (always the most common label)
- A straight-line model (logistic regression)
- A random forest
- (anything else you tried)

## Decision
Which model you will build on next, and why.

## Evidence
Copy the table from `docs/results/first_model.md` and add the confusion matrix (screenshot). Say how many Critical readings were missed, and how many false alarms were raised, on unseen patients.

## Consequences
- **Better:**
- **Worse:** (for example, a forest is harder to explain than a straight line: how will a clinician see why an alert fired?)
