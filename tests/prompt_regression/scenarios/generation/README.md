# Generation Prompt Regression Scenarios

These scenarios require live LLM calls for both the Generation module and the
LLM-as-judge evaluator. Each scenario makes two commodity-tier calls: one draft
generation call and one judge call.

Expected cost per full generation scenario run: 4 commodity-tier calls for the
two starter scenarios, normally less than USD 0.05 with mini/commodity models.
Actual cost depends on the injected provider configuration used on the Pi.
