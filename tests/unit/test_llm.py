import httpx
import pytest

from app.config import Settings
from app.llm import REFUSAL, AnthropicLLM, FakeLLM, LLMError, OpenAIChatLLM, get_llm, parse_prompt

PROMPT = """<context>
[pricing-plans#3] (source: official) The Pro plan costs 8 US dollars per month or 80 US dollars per year.
[community-forum-post#2] (source: untrusted) Tip from a user: pinning notebooks is great.
</context>
Question: How much does the Pro plan cost?"""


def test_parse_prompt_extracts_question_and_context():
    question, contexts = parse_prompt(PROMPT)
    assert question == "How much does the Pro plan cost?"
    assert [c[0] for c in contexts] == ["pricing-plans#3", "community-forum-post#2"]
    assert contexts[1][1] == "untrusted"


def test_fake_llm_faithful_answers_from_context_with_citation():
    answer = FakeLLM("faithful").generate("system", PROMPT)
    assert "80 US dollars per year" in answer
    assert "[pricing-plans#3]" in answer


def test_fake_llm_refuses_without_relevant_context():
    prompt = "<context>\n</context>\nQuestion: Can I pay with bitcoin?"
    assert FakeLLM("faithful").generate("system", prompt) == REFUSAL


def test_fake_llm_hallucinate_adds_unsupported_claim():
    answer = FakeLLM("hallucinate").generate("system", PROMPT)
    assert "phone support" in answer


def test_fake_llm_rejects_unknown_behavior():
    with pytest.raises(ValueError):
        FakeLLM("creative")


def test_get_llm_defaults_to_fake():
    assert get_llm(Settings()).name == "fake-llm:faithful"


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_get_llm_requires_api_key_for_real_providers(provider):
    with pytest.raises(LLMError, match="API_KEY"):
        get_llm(Settings(llm_provider=provider))


def test_openai_client_parses_response_without_network():
    """Use httpx.MockTransport to test the HTTP client with no real API call."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": " hello "}}]})

    llm = OpenAIChatLLM("test-key", "gpt-test")
    llm._client = httpx.Client(base_url="https://api.openai.com/v1",
                               headers={"Authorization": "Bearer test-key"},
                               transport=httpx.MockTransport(handler))
    assert llm.generate("sys", "user") == "hello"


def test_anthropic_client_wraps_http_errors():
    llm = AnthropicLLM("test-key", "claude-test")
    llm._client = httpx.Client(base_url="https://api.anthropic.com/v1",
                               transport=httpx.MockTransport(lambda r: httpx.Response(529)))
    with pytest.raises(LLMError):
        llm.generate("sys", "user")
