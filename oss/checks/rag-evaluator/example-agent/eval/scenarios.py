"""Giskard scenarios for the reference RAG agent."""

from __future__ import annotations

from giskard.checks import AnswerRelevance, Conformity, FnCheck, Groundedness, Scenario, Suite


def _has_retrieval(trace) -> bool:
    outputs = trace.last.outputs or {}
    return bool(outputs.get("sources") or outputs.get("context") or outputs.get("tool_calls"))


def _answer(trace) -> str:
    outputs = trace.last.outputs or {}
    if isinstance(outputs, dict):
        return str(outputs.get("answer", ""))
    return str(outputs)


def _source_doc_ids(trace) -> list[str]:
    outputs = trace.last.outputs or {}
    sources = outputs.get("sources") or []
    return [str(item.get("doc_id", "")) for item in sources if isinstance(item, dict)]


def _expected_doc_in_top_k(expected_doc_id: str, k: int = 3):
    """Build FnCheck verifying labelled doc_id appears in top-k sources."""

    def _check(trace) -> bool:
        ids = _source_doc_ids(trace)[:k]
        return expected_doc_id in ids

    return FnCheck(name=f"recall_hit_{expected_doc_id}_at_{k}", fn=_check)


refund_policy_in_scope = (
    Scenario("refund_policy_in_scope")
    .interact(inputs="What is the refund window for annual plans?")
    .check(FnCheck(name="retrieval_used", fn=lambda t: _has_retrieval(t)))
    .check(
        Groundedness(
            name="grounded_in_context",
            context_key='trace.last.outputs["context"]',
            answer_key='trace.last.outputs["answer"]',
        )
    )
    .check(AnswerRelevance(name="addresses_question"))
)

deployment_gcp = (
    Scenario("deployment_gcp")
    .interact(inputs="Which cloud provider does Acme Analytics use for production?")
    .check(FnCheck(name="retrieval_used", fn=lambda t: _has_retrieval(t)))
    .check(
        FnCheck(
            name="mentions_gcp",
            fn=lambda t: "gcp" in _answer(t).lower() or "google cloud" in _answer(t).lower(),
        )
    )
)

pricing_starter = (
    Scenario("pricing_starter")
    .interact(inputs="How much does the Starter plan cost per month?")
    .check(FnCheck(name="retrieval_used", fn=lambda t: _has_retrieval(t)))
    .check(
        FnCheck(name="mentions_starter_price", fn=lambda t: "49" in _answer(t))
    )
)

data_retention_logs = (
    Scenario("data_retention_logs")
    .interact(inputs="How long are query logs retained?")
    .check(FnCheck(name="retrieval_used", fn=lambda t: _has_retrieval(t)))
    .check(FnCheck(name="mentions_90_days", fn=lambda t: "90" in _answer(t)))
)

out_of_scope_aws = (
    Scenario("out_of_scope_aws_deploy")
    .interact(inputs="How do I deploy Acme Analytics to AWS?")
    .check(
        Conformity(
            name="declines_or_corrects_aws",
            rule=(
                "The agent must decline AWS deployment, state that only GCP is supported, "
                "or say it does not know — it must NOT provide AWS deployment instructions."
            ),
        )
    )
)

out_of_scope_weather = (
    Scenario("out_of_scope_weather")
    .interact(inputs="What is the weather in Paris today?")
    .check(
        Conformity(
            name="declines_off_topic",
            rule=(
                "The agent must decline or say it cannot answer because the topic is "
                "outside Acme Analytics documentation."
            ),
        )
    )
)

retrieval_refund_policy = (
    Scenario("retrieval_refund_policy_labelled")
    .interact(
        inputs="What is the refund window for annual subscriptions?",
        metadata={"expected_doc_ids": ["refund-policy"], "recall_k": 3},
    )
    .check(FnCheck(name="retrieval_used", fn=lambda t: _has_retrieval(t)))
    .check(_expected_doc_in_top_k("refund-policy", k=3))
)

STATIC_SCENARIOS = [
    refund_policy_in_scope,
    deployment_gcp,
    pricing_starter,
    data_retention_logs,
]

RETRIEVAL_LABELLED_SCENARIOS = [
    retrieval_refund_policy,
]

OOS_SCENARIOS = [
    out_of_scope_aws,
    out_of_scope_weather,
]


def build_suite(
    *,
    include_in_scope: bool = True,
    include_out_of_scope: bool = True,
    include_retrieval_labelled: bool = True,
) -> Suite:
    """Compose scenarios into a suite.

    Args:
        include_in_scope: Include KB-grounded scenarios.
        include_out_of_scope: Include refusal scenarios.
        include_retrieval_labelled: Include labelled recall@k scenarios.

    Returns:
        Configured giskard Suite.
    """
    suite = Suite(name="rag_example_eval")
    if include_in_scope:
        for scenario in STATIC_SCENARIOS:
            suite.append(scenario)
    if include_retrieval_labelled:
        for scenario in RETRIEVAL_LABELLED_SCENARIOS:
            suite.append(scenario)
    if include_out_of_scope:
        for scenario in OOS_SCENARIOS:
            suite.append(scenario)
    return suite
