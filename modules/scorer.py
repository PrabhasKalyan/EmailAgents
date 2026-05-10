"""
Fit scorer. High / Medium / Low.

Cheap path first: keyword match on description + industry. Only uses Gemini
for the ambiguous middle.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import companies_needing_scoring, update_company_score, get_conn
from modules.gemini_client import complete_text


CV_SUMMARY = """
Prabhas Kalyan — final-year Physics BS at IIT Kharagpur (CGPA 8.4, graduating 2027).
Targeting remote SDE / AI Engineer roles at US companies.

Internships:
- Imago AI: Text-to-SQL, RAG with Pinecone, ML model approval system on AWS S3.
- MoneyClub: RAG over a domain knowledge base, WhatsApp AI automation, fault-tolerant
  agentic chatbot — finetuned a transformer to 10ms latency, hybrid memory using inline
  context + memzero + pgvector for agent session persistence.
- Filo: DSL for AI video generation (Manim, MoviePy, OpenAI TTS), optics ray-diagram engine.
- PIN AI: macOS Electron app with on-device LLMs (Ollama), modular AI agents
  (Food / Travel / Shopping / Crypto), Ethereum ERC-8004 trustless agents on AWS.
- Marzi: video editing automation — hybrid deep-learning frame segmentation + AI-agent
  analysis, automated SEO/AEO blog pipeline (research → strategise → write → deploy).

Stack: Python, Go, Node.js, JavaScript, React, React Native, Django, Kafka, RabbitMQ,
Redis, Docker, Kubernetes, PostgreSQL, Pinecone, AWS, Celery, TensorFlow, PyTorch.
""".strip()


HIGH_KEYWORDS = [
    "ai", "artificial intelligence", "ml", "machine learning", "llm", "large language",
    "rag", "retrieval", "vector", "agent", "agents", "agentic",
    "video", "generative", "gen ai", "genai", "embedding",
    "distributed", "infrastructure", "platform", "developer tool", "devtool",
    "search", "database", "data infrastructure", "kafka", "kubernetes",
    "blockchain", "crypto", "ethereum", "web3",
]

LOW_KEYWORDS = [
    "real estate", "fashion", "apparel", "cosmetic", "beauty", "skincare",
    "restaurant", "food delivery only", "agriculture only", "farming",
    "consumer goods", "cannabis", "gambling",
]


def keyword_score(text):
    if not text:
        return None
    t = text.lower()
    if any(k in t for k in LOW_KEYWORDS):
        return "Low"
    hits = sum(1 for k in HIGH_KEYWORDS if k in t)
    if hits >= 2:
        return "High"
    if hits == 1:
        return "Medium"
    return None  # ambiguous → ask Gemini


def gemini_score(name, description, industry):
    prompt = f"""You are scoring whether a company is a good fit for a remote SDE / AI Engineer
candidate with the background below. Return EXACTLY one word: High, Medium, or Low.

Candidate background:
{CV_SUMMARY}

Scoring rubric:
- High: works on AI/ML, LLMs, RAG, distributed systems, backend infra, devtools, or video tech.
- Medium: general SDE roles at tech / SaaS / data companies.
- Low: non-tech, finance-only, hardware-only, or no engineering hiring.

Company: {name}
Industry: {industry or "unknown"}
Description: {description or "unknown"}

Return only one word."""
    out = complete_text(prompt).strip().split()[0].rstrip(".,!").capitalize()
    return out if out in ("High", "Medium", "Low") else "Medium"


def score_company(company):
    text = " ".join(filter(None, [company.get("description"), company.get("role")]))
    quick = keyword_score(text)
    if quick:
        return quick
    return gemini_score(
        company["name"],
        company.get("description"),
        company.get("role"),
    )


def score_batch(limit=None):
    rows = companies_needing_scoring(limit=limit)
    print(f"Scoring {len(rows)} companies")
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for i, c in enumerate(rows, 1):
        try:
            score = score_company(c)
        except Exception as e:
            print(f"[{i}/{len(rows)}] {c['name']}  error: {e}")
            continue
        update_company_score(c["id"], score)
        counts[score] = counts.get(score, 0) + 1
        if i % 25 == 0 or i == len(rows):
            print(f"[{i}/{len(rows)}] running counts: {counts}")
    print(f"Done. {counts['High']} High, {counts['Medium']} Medium, {counts['Low']} Low.")
    return counts


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    score_batch(limit=n)
