from subscription_reasoning_bench.models import Task
from subscription_reasoning_bench.scoring import bbeh_match, extract_final_answer, score_response


def test_extract_final_answer_prefers_last_tag():
    response = "draft <final_answer>A</final_answer>\n<final_answer>B</final_answer>"
    assert extract_final_answer(response) == "B"


def test_bbeh_match_handles_common_format_variants():
    assert bbeh_match("\\boxed{4}", "4")
    assert bbeh_match("(A)", "a")
    assert bbeh_match("2, 3, 4", "2,3,4")
    assert not bbeh_match("(B)", "a")


def test_exact_score_is_normalized():
    task = Task("one", "question", "Yes")
    answer, score = score_response(task, "reasoning\n<final_answer>**YES**.</final_answer>")
    assert answer == "**YES**."
    assert score == 1.0
