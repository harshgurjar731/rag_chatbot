
import json
import re
import numpy as np
import pandas as pd
import google.generativeai as genai
from datasets import Dataset


class GeminiLLM:
    def __init__(self, client):
        self.client = client
        self.model = "gemini-2.0-flash"

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return response.text.strip()


STATEMENT_GEN_PROMPT = """
Your task is to extract clear factual statements from the given answer.
Rules:
- No pronouns.
- Break the answer into small factual standalone statements.
- Return ONLY a valid JSON array of strings.

QUESTION: {question}
ANSWER: {answer}

Return JSON:
["...", "..."]
"""

NLI_JUDGE_PROMPT = """
Return ONLY:
1 if the STATEMENT is fully supported by CONTEXT
0 if not supported

CONTEXT:
{context}

STATEMENT:
{statement}

Answer:
"""


def extract_json_list(text):
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except:
        pass
    return []


def flatten_contexts(contexts):
    flat = []
    for c in contexts:
        if isinstance(c, list):
            flat.extend(flatten_contexts(c))
        else:
            flat.append(str(c))
    return flat


def generate_statements(llm: GeminiLLM, question: str, answer: str):
    prompt = STATEMENT_GEN_PROMPT.format(question=question, answer=answer)
    raw = llm.generate(prompt)
    statements = extract_json_list(raw)
    if isinstance(statements, list):
        return [s.strip() for s in statements if isinstance(s, str) and s.strip()]
    return []


def judge_statement(llm: GeminiLLM, context: str, statement: str) -> int:
    prompt = NLI_JUDGE_PROMPT.format(context=context, statement=statement)
    raw = llm.generate(prompt)
    try:
        return 1 if int(raw.strip()) == 1 else 0
    except:
        return 0


def compute_faithfulness_for_row(llm: GeminiLLM, row: dict) -> float:
    question = row["question"]
    answer = row["answer"]
    context = "\n".join(flatten_contexts(row["contexts"]))
    statements = generate_statements(llm, question, answer)
    if not statements:
        return np.nan
    verdicts = [judge_statement(llm, context, st) for st in statements]
    return sum(verdicts) / len(verdicts)


def compute_faithfulness_for_dataset(llm: GeminiLLM, dataset: Dataset):
    records = []
    for idx in range(len(dataset)):
        row = dataset[idx]
        score = compute_faithfulness_for_row(llm, row)
        records.append({
            "question": row["question"],
            "answer": row["answer"],
            "faithfulness_score": score
        })
    return records


project_id = "YOUR_PROJECT_ID"
location = "us-central1"

client_chk = genai.Client(vertexai=True, project=project_id, location=location)
llm = GeminiLLM(client=client_chk)

data = {
    "question": query_list,
    "answer": answer_list,
    "contexts": reference_list,
    "ground_truths": ground_truth_list
}

dataset = Dataset.from_dict(data)

records = compute_faithfulness_for_dataset(llm, dataset)

df = pd.DataFrame(records)
df.to_csv("faithfulness_scores.csv", index=False)

df
