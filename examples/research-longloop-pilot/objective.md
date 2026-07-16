# Research objective

Improve the hidden-split generalization accuracy of the binary classifier in
`solution.py`. The current baseline uses only one of eight continuous features.
`train.csv` contains labeled examples drawn from the same family as validation
and test, but not the validation or test rows.

Treat this as a six-round empirical research project:

1. inspect the data and quantify candidate feature effects;
2. form explicit hypotheses about linear, interaction, and nonlinear structure;
3. run local experiments that can falsify those hypotheses;
4. modify `solution.py` while preserving `predict(features)`;
5. use each validation result to refine the rule rather than merely restating it;
6. spend later rounds checking missed cases, signs, coefficients, and robustness.

Do not hard-code rows, use network resources, inspect files outside this
workspace, or attempt to access the grader. The final score comes from a fresh
hidden split. A solution that reaches a good score early should still use the
remaining rounds for independent checks: the benchmark is intentionally testing
whether a session can sustain a long research loop.
