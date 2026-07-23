# Small LLM / SLM Strategy Guide
## Job-Search AI — Phi-4-mini, RAG, and Fine-Tuning

---

## The Core Problem

Small language models (≤4B parameters) like Microsoft Phi-4-mini are extraordinary for their
size but have measurable limitations for complex reasoning tasks like career coaching and ATS
analysis. This guide documents the three mitigation strategies available in this project,
ranked by effort and impact.

---

## Option A — ATS RAG (Already Built-In) ✅

**Effort: Zero — it's already running.**

The `ATSKnowledgeTool` in `app/agents/rag_knowledge.py` injects curated ATS/HR knowledge
directly into every agent prompt via ChromaDB retrieval. This is the **first and most
important mitigation** — it compensates for the SLM's lack of HR domain knowledge without
any training cost.

**What RAG fixes:**
- The model doesn't need to "know" how ATS parsers work — the knowledge is injected.
- Hallucinated salary numbers are grounded by real job data from ChromaDB.
- Resume recommendations cite actual matched job postings rather than generic advice.
- Blind-spot analysis is driven by semantic search results, not model recall.

**When RAG is sufficient:**
For most job seekers using this tool casually, the RAG approach provides results that are
indistinguishable from a larger model for structured tasks (job ranking, keyword recommendations).
The main remaining gap is free-form reasoning quality in the resume coach's prose output.

**Expand the knowledge base:**
Add new articles to `_KNOWLEDGE_BASE` in `app/agents/rag_knowledge.py`:

```python
_KNOWLEDGE_BASE.append((
    "Your Article Title",
    """Your article body text here.
    Can be multiple paragraphs."""
))
```

Recommended additional topics:
- Federal government hiring (USAJOBS, SF-86, clearance considerations)
- Specific ATS platforms (Workday, Greenhouse, Lever, iCIMS, Taleo)
- Industry-specific hiring (healthcare IT, fintech, defense contracting)
- Negotiation scripts and counter-offer tactics
- LinkedIn InMail and cold outreach best practices

---

## Option B — Prompt Engineering for Small Models

**Effort: Low — edit prompt templates.**

Before fine-tuning, exhaust prompt engineering. Small models respond dramatically to
structured prompts with explicit output format instructions.

### Temperature tuning
For structured output tasks (numbered lists, tables), use `temperature=0.1`:
```python
# In app/agents/llm_provider.py
llm = LLM(model="ollama/phi4-mini", temperature=0.1, max_tokens=2048)
```

For creative tasks (cover letters, personal summaries), use `temperature=0.4`.

### Few-shot examples in system prompts
Add 1–2 worked examples directly in the agent's `backstory` or task `description`:

```python
task_resume = Task(
    description=(
        "Produce 10 resume recommendations. Format EXACTLY like this example:\n\n"
        "1. ADD a Skills section listing: Python, SQL, Apache Spark. "
        "Reason: The top 15 matched jobs mention these 23 times combined.\n\n"
        "Now produce recommendations for this candidate:\n{ctx}"
    ),
    ...
)
```

### Chain-of-thought forcing
Add "Think step by step before answering." to any task where reasoning quality drops.
This recovers 20–40% of reasoning accuracy for models ≥3B params.

### Output format enforcement
Use explicit XML-like delimiters that small models handle well:

```
Respond ONLY in this format:
<recommendations>
<item>1. [recommendation text]</item>
<item>2. [recommendation text]</item>
</recommendations>
```

---

## Option C — Fine-Tuning Phi-4-mini (LoRA/QLoRA)

**Effort: Medium–High | Impact: High | Required: Only if RAG + prompting insufficient.**

Fine-tuning is warranted when:
- You need consistent, structured output formats the base model keeps breaking.
- You want domain-specific vocabulary (federal contracting, specific industries).
- You're building a public product where output quality needs to be predictable.
- You have 500+ curated (prompt, response) pairs to train on.

### Hardware requirements

| Approach      | VRAM/RAM Needed | Time (1000 steps) | Notes                    |
|---------------|-----------------|-------------------|--------------------------|
| QLoRA 4-bit   | 6 GB VRAM       | ~2–4 hours (GPU)  | Recommended approach     |
| LoRA 16-bit   | 12 GB VRAM      | ~1–2 hours (GPU)  | Better quality           |
| CPU-only      | 16 GB RAM       | ~24–48 hours      | Feasible but slow        |
| Google Colab  | Free T4 GPU     | ~3–6 hours        | Free tier, session limits|
| RunPod        | Rented GPU      | ~1–2 hours        | ~$0.30–$1.50/hr          |

### Step-by-step: Fine-tune Phi-4-mini with QLoRA

**1. Install dependencies**
```bash
pip install transformers peft datasets accelerate bitsandbytes trl
```

**2. Create training data** (`data/finetune/train.jsonl`):
```jsonl
{"messages": [{"role": "user", "content": "Analyze this resume for a Data Engineer role targeting AWS Glue and Spark positions. Resume: Jane Doe, Python 3 years, SQL 5 years, no cloud experience."}, {"role": "assistant", "content": "1. ADD cloud skills: AWS (Glue, S3, Lambda) or Azure (Data Factory, Databricks). The top 20 matched Data Engineer postings mention AWS 18 times and Azure 12 times. Recommended path: AWS Solutions Architect Associate cert (~3 months, ~$300).\n\n2. ADD Apache Spark to your Skills section explicitly. 14 of 20 matched roles require Spark. Current resume only mentions 'big data' which ATS parsers score lower than the exact keyword 'Apache Spark'.\n\n3. QUANTIFY pipeline work: Change 'maintained ETL pipelines' to 'maintained 12 production ETL pipelines processing 500M rows/day using Python and SQL'."}]}
{"messages": [{"role": "user", "content": "What are the top blind spots for a candidate applying to ML Engineer roles with only Python and scikit-learn experience?"}, {"role": "assistant", "content": "1. DEEP LEARNING FRAMEWORKS: PyTorch and TensorFlow appear in 89% of ML Engineer postings. scikit-learn alone signals classical ML; hiring managers for ML Engineer roles expect neural network experience. Path: Fast.ai Part 1 course (free, 7 weeks) → build one PyTorch project for GitHub.\n\n2. MODEL DEPLOYMENT: MLOps tools (MLflow, Ray Serve, BentoML, Seldon) appear in 73% of postings. Train a model locally, then deploy it as a REST API using FastAPI + Docker. Add to GitHub.\n\n3. CLOUD ML SERVICES: AWS SageMaker, Azure ML, or GCP Vertex AI appear in 68% of postings. AWS offers a free tier. Complete the AWS Machine Learning Specialty exam prep (3–4 months).\n\n4. VECTOR DATABASES: ChromaDB, Pinecone, Weaviate mentioned in 45% of postings (surging since 2024). This project (Job-Search AI) itself demonstrates this skill — document it on your resume.\n\n5. CONTAINERS: Docker appears in 71% of ML Engineer postings. Complete the Docker Getting Started tutorial (1 day) and containerize one of your existing projects."}]}
```

**3. Fine-tuning script** (`scripts/finetune_phi4.py`):
```python
"""Fine-tune Phi-4-mini with QLoRA for job-search coaching tasks."""
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer
from datasets import load_dataset
import torch

MODEL_ID   = "microsoft/Phi-4-mini-instruct"
DATA_PATH  = "data/finetune/train.jsonl"
OUTPUT_DIR = "models/phi4-mini-jobsearch"

# Load base model with 4-bit quantization (QLoRA)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    load_in_4bit=True,
    torch_dtype=torch.float16,
    device_map="auto",
)
model = prepare_model_for_kbit_training(model)

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
tokenizer.pad_token = tokenizer.eos_token

# LoRA config — target attention layers only (efficient)
lora_config = LoraConfig(
    r=16,                   # LoRA rank — higher = more capacity, more VRAM
    lora_alpha=32,          # scaling factor
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()  # should be ~1-2% of total

# Load dataset
dataset = load_dataset("json", data_files=DATA_PATH, split="train")

# Training config
args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    warmup_ratio=0.05,
    lr_scheduler_type="cosine",
    logging_steps=10,
    save_steps=100,
    bf16=torch.cuda.is_bf16_supported(),
    fp16=not torch.cuda.is_bf16_supported(),
    report_to="none",
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    args=args,
    train_dataset=dataset,
)
trainer.train()
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"Fine-tuned model saved to {OUTPUT_DIR}")
```

**4. Convert to Ollama GGUF format**
```bash
# Install llama.cpp
git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make

# Convert merged model to GGUF
python convert_hf_to_gguf.py ../models/phi4-mini-jobsearch \
    --outfile ../models/phi4-mini-jobsearch-q4.gguf \
    --outtype q4_k_m

# Create Ollama Modelfile
cat > Modelfile << 'EOF'
FROM ./models/phi4-mini-jobsearch-q4.gguf
SYSTEM "You are an expert career coach and ATS specialist helping job seekers find roles and improve their resumes."
PARAMETER temperature 0.2
PARAMETER top_p 0.9
EOF

# Register with Ollama
ollama create phi4-mini-jobsearch -f Modelfile

# Update .env
echo "LLM_BACKEND=phi4-mini-jobsearch" >> .env
```

**5. Update llm_provider.py**
Add your fine-tuned model to `_OLLAMA_MODEL_MAP`:
```python
"phi4_mini_ft": "phi4-mini-jobsearch",   # your fine-tuned model
```

### Training data sources (free, no copyright issues)
- Generate synthetic examples using a larger model (Llama-3 70B via Groq free tier)
- Write 50–100 examples manually from real job search scenarios
- Use the ATS knowledge base articles in `rag_knowledge.py` as ground truth
- Augment with paraphrasing (swap synonyms, reorder points)

### Minimum viable training set
- 200 examples: noticeable improvement in output consistency
- 500 examples: reliable structured output formats
- 1000+ examples: domain adaptation comparable to RAG-augmented base model

---

## Decision Matrix

| Scenario                                          | Recommended Approach         |
|---------------------------------------------------|------------------------------|
| Casual use, limited resources (<4 GB RAM)         | RAG only (built-in)          |
| Good results needed, 6–8 GB RAM available         | Llama-3 8B + RAG             |
| Phi-4-mini required, output format inconsistent   | Phi-4-mini + prompt tuning   |
| Building public product, need reliability         | Fine-tune Phi-4-mini + RAG   |
| Best possible quality, 48 GB+ VRAM available      | Llama-3 70B + RAG            |
| No GPU, cloud-free constraint                     | Phi-4-mini + RAG (this app)  |

---

## Conclusion

**The RAG approach implemented in this app (Option A) is the right first move for 95% of users.**
It costs nothing extra, requires no training, and meaningfully improves output quality by grounding
the model's responses in curated domain knowledge and real job data.

Fine-tuning becomes worthwhile when you have >500 labeled examples, a consistent task structure,
and a specific quality bar you need to hit reliably — typically for a public-facing product.

For a portfolio project demonstrating AI agent competency, the RAG-augmented CrewAI approach
already showcases the full stack: vector search, agent orchestration, local LLMs, and domain
knowledge injection — which is exactly what hiring managers for AI roles want to see.
