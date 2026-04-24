from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)

completion = client.chat.completions.create(
  model="openai/gpt-oss-120b",
  messages=[{"role":"user","content":"Hello"}],
  temperature=1,
  top_p=1,
  max_tokens=4096,
  stream=True
)

for chunk in completion:
  if not getattr(chunk, "choices", None):
    continue
  reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
  if reasoning:
    print(reasoning, end="")
  if chunk.choices and chunk.choices[0].delta.content is not None:
    print(chunk.choices[0].delta.content, end="")

