# Research objective

Improve the generalization accuracy of the classifier implemented in
`solution.py`. The current baseline uses only one feature. You are given
`train.csv`, which contains four continuous features and binary labels.

Treat this as a small empirical research task:

1. inspect the data and form hypotheses about the decision rule;
2. run local analyses or experiments;
3. modify `solution.py`;
4. preserve the public `predict(features)` interface;
5. do not hard-code individual rows or read files outside this workspace.

The harness evaluates a fresh validation split after each research round and
returns deterministic PI feedback. A separate hidden split determines the
final score.

