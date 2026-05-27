from __future__ import annotations

import pytest

from tests.prompt_regression.judge import JudgeResult, LLMJudge


class FakeLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_llm_judge_parses_pass_response_and_forwards_request():
    client = FakeLLMClient("PASS|The response respects the constraint.")
    judge = LLMJudge(client, llm_config={"provider": "openai"}, tier="commodity")

    result = await judge.evaluate(
        response_text="We will not join the forbidden alliance.",
        criteria="The response refuses the alliance.",
        pass_instruction="Pass when it refuses.",
        fail_instruction="Fail when it accepts.",
        context="CONSTRAINT: Do not ally with France.",
    )

    assert result == JudgeResult(
        verdict="PASS",
        explanation="The response respects the constraint.",
        criteria="The response refuses the alliance.",
    )
    assert client.calls[0]["config"] == {"provider": "openai"}
    assert client.calls[0]["tier"] == "commodity"
    assert client.calls[0]["messages"][0]["role"] == "system"
    assert "PASS|explanation" in client.calls[0]["messages"][0]["content"]
    assert "CONSTRAINT: Do not ally with France." in client.calls[0]["messages"][1][
        "content"
    ]


@pytest.mark.asyncio
async def test_llm_judge_parses_fail_response():
    judge = LLMJudge(FakeLLMClient("FAIL|The response accepts the alliance."), {})

    result = await judge.evaluate(
        response_text="We accept the alliance.",
        criteria="Must refuse the alliance.",
        pass_instruction="Pass when refused.",
        fail_instruction="Fail when accepted.",
    )

    assert result.verdict == "FAIL"
    assert result.explanation == "The response accepts the alliance."
    assert result.criteria == "Must refuse the alliance."


@pytest.mark.asyncio
async def test_llm_judge_rejects_malformed_response():
    judge = LLMJudge(FakeLLMClient("MAYBE because it is unclear"), {})

    with pytest.raises(ValueError, match="separator"):
        await judge.evaluate(
            response_text="Maybe.",
            criteria="Must be decisive.",
            pass_instruction="Pass when decisive.",
            fail_instruction="Fail when unclear.",
        )
