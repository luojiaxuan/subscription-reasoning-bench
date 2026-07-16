# Autonomous research objective

Improve the hidden-split generalization accuracy of the binary classifier in
`solution.py`. The current baseline uses only one of eight continuous features.
`train.csv` contains labeled examples drawn from the same family as validation
and test, but not the validation or test rows.

This is one uninterrupted autonomous research turn. Do not stop after forming
the first plausible rule. Use the available time to run a genuine empirical
loop inside the workspace:

1. inspect the data and quantify candidate feature effects;
2. form explicit hypotheses about linear, interaction, and nonlinear structure;
3. write and run local experiments that can falsify those hypotheses;
4. revise `solution.py` while preserving `predict(features)`;
5. test missed cases, signs, coefficients, and robustness;
6. finish only after an independent verification pass supports the submitted rule.

Do not hard-code rows, use network resources, inspect files outside this
workspace, or attempt to access the grader. The final score comes from a fresh
hidden split.
