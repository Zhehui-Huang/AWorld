# Workflow Example: Find, Download, and Summarize arXiv Paper

This document provides a step-by-step walkthrough of how the multi-agent system handles a complex task.

## Task Definition

**User Request:**
> "Find a paper on arXiv that was published in August 2020 about attention mechanisms in transformers. Download the PDF file, then extract the content and provide a comprehensive summary of approximately 1000 words."

---

## Execution Flow

### Phase 1: Task Reception and Analysis

```
┌─────────────────────────────────────────────────────────────┐
│                           User                              │
│                                                             │
│  Input: "Find arXiv paper from Aug 2020 about attention   │
│          mechanisms, download it, and summarize in 1000    │
│          words"                                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Task submitted
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Main Orchestrator Agent                        │
│                                                             │
│  Reasoning:                                                 │
│  1. Analyze task: This is a complex multi-step task        │
│  2. Break down requirements:                               │
│     - Search for specific paper (arXiv, Aug 2020)         │
│     - Download the PDF file                                │
│     - Extract content from PDF                             │
│     - Generate 1000-word summary                           │
│                                                             │
│  3. Identify needed agents:                                │
│     - search_agent (for finding and downloading)           │
│     - pdf_agent (for extraction and summarization)         │
│                                                             │
│  4. Plan execution:                                         │
│     Step 1: Delegate search + download to search_agent    │
│     Step 2: Delegate extraction + summary to pdf_agent    │
│     Step 3: Synthesize final answer                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           └─> Proceeding to Phase 2
```

---

### Phase 2: Search and Download Delegation

```
┌─────────────────────────────────────────────────────────────┐
│              Main Orchestrator Agent                        │
│                                                             │
│  Decision: Need to search for and download the paper       │
│  Action: Delegate to search_agent                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Tool Call:
                           │ search_agent.mcp_create_search_agent(
                           │   task_prompt="Find and download a paper
                           │                on arXiv from August 2020
                           │                about attention mechanisms
                           │                in transformers or NMT",
                           │   name="arxiv_search_agent",
                           │   max_steps=15
                           │ )
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         Search Agent Service (SearchAgentCollection)        │
│                                                             │
│  1. Generate agent_id: "search_agent_a1b2c3d4"            │
│  2. Load LLM config from environment                       │
│  3. Create Agent instance with:                            │
│     - Dedicated LLM (GPT-4)                               │
│     - Own memory module                                    │
│     - MCP tools: search, download                         │
│  4. Register agent in registry                             │
│  5. Create Task with agent                                 │
│  6. Execute task → Agent reasoning begins                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Agent starts autonomous execution
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│             Search Agent Instance (Autonomous)              │
│  Agent ID: search_agent_a1b2c3d4                           │
│  System Prompt: "You are a focused search agent..."       │
│                                                             │
│  ┌────────── Reasoning Loop (Think-Act-Observe) ────────┐ │
│  │                                                        │ │
│  │  Step 1: Think                                        │ │
│  │  "I need to search arXiv for papers from August      │ │
│  │   2020 about attention mechanisms. I'll use Google   │ │
│  │   Custom Search with site:arxiv.org filter."         │ │
│  │                                                        │ │
│  │  Step 2: Act                                          │ │
│  │  Tool: search.mcp_search_google(                     │ │
│  │    query="site:arxiv.org attention mechanisms        │ │
│  │            transformers August 2020",                │ │
│  │    num_results=5                                     │ │
│  │  )                                                    │ │
│  │                                                        │ │
│  │  Step 3: Observe                                      │ │
│  │  Results received:                                    │ │
│  │  - Paper 1: "Attention Is All You Need Revisited"   │ │
│  │    URL: https://arxiv.org/abs/2008.12345            │ │
│  │  - Paper 2: "Efficient Attention Mechanisms"        │ │
│  │    URL: https://arxiv.org/abs/2008.23456            │ │
│  │  - ... (more results)                                │ │
│  │                                                        │ │
│  │  Step 4: Think                                        │ │
│  │  "Found relevant papers. Paper 1 looks most         │ │
│  │   relevant. I'll download it. Need to convert       │ │
│  │   abs URL to pdf URL."                               │ │
│  │                                                        │ │
│  │  Step 5: Act                                          │ │
│  │  Tool: download.mcp_download_file(                   │ │
│  │    url="https://arxiv.org/pdf/2008.12345.pdf",      │ │
│  │    output_file_path="arxiv_2008_12345.pdf"          │ │
│  │  )                                                    │ │
│  │                                                        │ │
│  │  Step 6: Observe                                      │ │
│  │  Download successful!                                 │ │
│  │  File saved to: /workspace/arxiv_2008_12345.pdf     │ │
│  │  File size: 2.3 MB                                   │ │
│  │                                                        │ │
│  │  Step 7: Think                                        │ │
│  │  "Task complete. I found the paper and downloaded   │ │
│  │   it successfully. I'll return the file path."      │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Final Answer:                                              │
│  "Successfully found and downloaded paper:                  │
│   Title: Attention Is All You Need Revisited               │
│   arXiv ID: 2008.12345                                     │
│   Published: August 2020                                    │
│   Downloaded to: /workspace/arxiv_2008_12345.pdf          │
│   This paper discusses improvements to the attention       │
│   mechanism in transformer architectures..."               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Return ActionResponse
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Main Orchestrator Agent                        │
│                                                             │
│  Received from search_agent:                               │
│  {                                                          │
│    "success": true,                                        │
│    "agent_id": "search_agent_a1b2c3d4",                   │
│    "answer": "Successfully found and downloaded paper...", │
│    "metadata": {                                           │
│      "file_path": "/workspace/arxiv_2008_12345.pdf",     │
│      "arxiv_id": "2008.12345",                           │
│      "title": "Attention Is All You Need Revisited"       │
│    }                                                        │
│  }                                                          │
│                                                             │
│  Reasoning:                                                 │
│  "Great! The search agent found and downloaded the paper.  │
│   Now I need to extract the content and create a summary.  │
│   I'll delegate this to the pdf_agent."                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           └─> Proceeding to Phase 3
```

---

### Phase 3: PDF Extraction and Summarization

```
┌─────────────────────────────────────────────────────────────┐
│              Main Orchestrator Agent                        │
│                                                             │
│  Decision: Need to extract and summarize the PDF           │
│  Action: Delegate to pdf_agent                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Tool Call:
                           │ pdf_agent.mcp_create_pdf_agent(
                           │   task_prompt="Extract content from
                           │                /workspace/arxiv_2008_12345.pdf
                           │                and create a comprehensive
                           │                1000-word summary covering:
                           │                1. Main research question
                           │                2. Proposed approach
                           │                3. Key findings
                           │                4. Significance",
                           │   name="paper_analysis_agent",
                           │   max_steps=15
                           │ )
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           PDF Agent Service (PDFAgentCollection)            │
│                                                             │
│  1. Generate agent_id: "pdf_agent_e5f6g7h8"               │
│  2. Load LLM config from environment                       │
│  3. Create Agent instance with:                            │
│     - Dedicated LLM (GPT-4)                               │
│     - Own memory module                                    │
│     - MCP tools: pdf extraction                           │
│  4. Register agent in registry                             │
│  5. Create Task with agent                                 │
│  6. Execute task → Agent reasoning begins                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Agent starts autonomous execution
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               PDF Agent Instance (Autonomous)               │
│  Agent ID: pdf_agent_e5f6g7h8                              │
│  System Prompt: "You are a focused PDF processing agent..." │
│                                                             │
│  ┌────────── Reasoning Loop (Think-Act-Observe) ────────┐ │
│  │                                                        │ │
│  │  Step 1: Think                                        │ │
│  │  "I need to extract content from the PDF at          │ │
│  │   /workspace/arxiv_2008_12345.pdf. I'll use the     │ │
│  │   pdf extraction tool."                               │ │
│  │                                                        │ │
│  │  Step 2: Act                                          │ │
│  │  Tool: pdf.mcp_extract_document_content(             │ │
│  │    file_path="/workspace/arxiv_2008_12345.pdf",     │ │
│  │    output_format="markdown",                         │ │
│  │    extract_images=false                              │ │
│  │  )                                                    │ │
│  │                                                        │ │
│  │  Step 3: Observe                                      │ │
│  │  Extraction successful!                               │ │
│  │  Content received (15 pages, ~6000 words):           │ │
│  │                                                        │ │
│  │  # Attention Is All You Need Revisited               │ │
│  │  ## Abstract                                          │ │
│  │  We propose improvements to the attention mechanism  │ │
│  │  in transformer architectures...                      │ │
│  │                                                        │ │
│  │  ## 1. Introduction                                   │ │
│  │  The transformer architecture has revolutionized...   │ │
│  │                                                        │ │
│  │  [Full content extracted...]                          │ │
│  │                                                        │ │
│  │  Step 4: Think                                        │ │
│  │  "I have the full content. Now I need to analyze    │ │
│  │   it and create a 1000-word summary covering the    │ │
│  │   4 requested points. Let me identify:               │ │
│  │   1. Main research question (from intro)             │ │
│  │   2. Proposed approach (from methods)                │ │
│  │   3. Key findings (from results)                     │ │
│  │   4. Significance (from conclusion)"                 │ │
│  │                                                        │ │
│  │  Step 5: Analyze and Synthesize                      │ │
│  │  Reading through content...                           │ │
│  │  - Research question: How to improve attention       │ │
│  │    efficiency while maintaining performance          │ │
│  │  - Approach: Novel sparse attention pattern          │ │
│  │  - Findings: 30% faster, same accuracy               │ │
│  │  - Significance: Enables longer sequences            │ │
│  │                                                        │ │
│  │  Step 6: Generate Summary                            │ │
│  │  Creating 1000-word summary...                        │ │
│  │  [Writing comprehensive summary...]                   │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Final Answer:                                              │
│  "Comprehensive Summary (1000 words):                       │
│                                                             │
│   ## Main Research Question and Motivation                 │
│   This paper addresses the computational inefficiency      │
│   of standard attention mechanisms in transformer          │
│   architectures, particularly when processing long         │
│   sequences. The authors observe that while transformers   │
│   have achieved state-of-the-art results across multiple  │
│   NLP tasks, the quadratic complexity of self-attention   │
│   (O(n²)) becomes prohibitive for sequences longer than   │
│   a few thousand tokens...                                 │
│                                                             │
│   ## Proposed Attention Mechanism                          │
│   The paper introduces a novel sparse attention pattern   │
│   called 'Adaptive Sparse Attention' (ASA). Unlike        │
│   previous approaches that use fixed sparsity patterns... │
│                                                             │
│   [... continues for ~1000 words ...]                      │
│                                                             │
│   ## Significance and Contributions                        │
│   This work makes several important contributions to the  │
│   field of neural machine translation and transformer     │
│   architectures..."                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Return ActionResponse
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Main Orchestrator Agent                        │
│                                                             │
│  Received from pdf_agent:                                  │
│  {                                                          │
│    "success": true,                                        │
│    "agent_id": "pdf_agent_e5f6g7h8",                      │
│    "answer": "Comprehensive Summary (1000 words)...",     │
│    "metadata": {                                           │
│      "word_count": 1023,                                  │
│      "extracted_pages": 15                                │
│    }                                                        │
│  }                                                          │
│                                                             │
│  Reasoning:                                                 │
│  "Perfect! I now have:                                     │
│   1. Paper details from search_agent                       │
│   2. Comprehensive summary from pdf_agent                  │
│   I'll synthesize these into a final answer for the user." │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           └─> Proceeding to Phase 4
```

---

### Phase 4: Result Synthesis and Return

```
┌─────────────────────────────────────────────────────────────┐
│              Main Orchestrator Agent                        │
│                                                             │
│  Final Synthesis:                                           │
│  Combining information from both agents...                  │
│                                                             │
│  Information gathered:                                      │
│  - Paper title: "Attention Is All You Need Revisited"     │
│  - arXiv ID: 2008.12345                                    │
│  - Publication: August 2020                                 │
│  - File location: /workspace/arxiv_2008_12345.pdf         │
│  - Summary: [1000-word comprehensive summary]              │
│                                                             │
│  Formatting final answer...                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Final Answer
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                          User                               │
│                                                             │
│  ✅ Task Completed Successfully!                           │
│                                                             │
│  # arXiv Paper Analysis: Attention Mechanisms               │
│                                                             │
│  ## Paper Details                                           │
│  - **Title:** Attention Is All You Need Revisited          │
│  - **arXiv ID:** 2008.12345                                │
│  - **Published:** August 2020                               │
│  - **Downloaded:** /workspace/arxiv_2008_12345.pdf        │
│  - **Pages:** 15                                           │
│                                                             │
│  ## Comprehensive Summary (1000 words)                      │
│                                                             │
│  ### Main Research Question and Motivation                 │
│  This paper addresses the computational inefficiency of    │
│  standard attention mechanisms in transformer              │
│  architectures, particularly when processing long          │
│  sequences...                                               │
│                                                             │
│  ### Proposed Attention Mechanism                          │
│  The paper introduces a novel sparse attention pattern    │
│  called 'Adaptive Sparse Attention' (ASA)...              │
│                                                             │
│  ### Key Findings and Results                              │
│  The experimental evaluation demonstrates several          │
│  important results...                                       │
│                                                             │
│  ### Significance and Contributions                        │
│  This work makes several important contributions to the   │
│  field...                                                   │
│                                                             │
│  ---                                                        │
│  Task completed using:                                      │
│  - Search Agent (search_agent_a1b2c3d4): Found & downloaded│
│  - PDF Agent (pdf_agent_e5f6g7h8): Extracted & summarized │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary Statistics

### Execution Metrics

| Metric | Value |
|--------|-------|
| **Total Execution Time** | ~45 seconds |
| **Main Agent Steps** | 5 steps |
| **Search Agent Steps** | 7 steps |
| **PDF Agent Steps** | 6 steps |
| **Total Agent Steps** | 18 steps |
| **Tool Calls** | 3 calls (search, download, extract) |
| **Agents Created** | 2 agents |
| **Files Downloaded** | 1 file (2.3 MB) |
| **Summary Word Count** | 1023 words |

### Agent Collaboration

```
Main Agent (Orchestrator)
├─> Delegated search task → Search Agent
│   └─> Search Agent used: search.mcp_search_google(), download.mcp_download_file()
├─> Delegated analysis task → PDF Agent
│   └─> PDF Agent used: pdf.mcp_extract_document_content()
└─> Synthesized final answer
```

### Token Usage Breakdown

```
Main Agent:       ~2,500 tokens
  - System prompt: 800 tokens
  - Task analysis: 300 tokens
  - Delegation:    400 tokens
  - Synthesis:     1,000 tokens

Search Agent:     ~1,800 tokens
  - System prompt: 600 tokens
  - Reasoning:     500 tokens
  - Results:       700 tokens

PDF Agent:        ~4,200 tokens
  - System prompt: 600 tokens
  - Content:       2,500 tokens
  - Summary:       1,100 tokens

Total:            ~8,500 tokens
```

---

## Key Observations

### 1. Autonomous Sub-Agent Behavior

Each sub-agent worked independently:
- **Search Agent:** Decided to use Google CSE, chose search terms, selected best result, downloaded file
- **PDF Agent:** Extracted content, analyzed structure, identified key sections, generated summary

### 2. Specialization Benefits

- **Search Agent** focused only on finding and retrieving the paper
- **PDF Agent** focused only on extraction and analysis
- **Main Agent** handled high-level coordination

### 3. Memory Isolation

- Each agent maintained its own context
- No cross-contamination between agents
- Main agent synthesized information from both

### 4. Error Handling

If any step had failed:
- Search Agent could try alternative search terms
- PDF Agent could retry with OCR if extraction failed
- Main Agent could try alternative approaches or report error

---

## Alternative Workflows

### Workflow 2: Agent Reuse

If we had multiple related tasks:

```
Task 1: Find paper A
  └─> Create search_agent_1 ✓

Task 2: Find paper B (same author)
  └─> Reuse search_agent_1 ✓ (remembers previous search context)

Task 3: Analyze both papers
  └─> Create pdf_agent_1 for both ✓
```

### Workflow 3: Parallel Processing (Future)

For independent subtasks:

```
Main Agent
  ├─> Task 1 (search paper 1) → search_agent_1 ┐
  ├─> Task 2 (search paper 2) → search_agent_2 ├─> Parallel
  └─> Wait for both                             ┘
      └─> Task 3 (compare) → pdf_agent_1
```

---

## Lessons Learned

1. **Clear Task Decomposition:** Main agent effectively broke down complex task
2. **Appropriate Delegation:** Right agent for each subtask
3. **Result Synthesis:** Main agent added value by combining results
4. **Autonomous Execution:** Sub-agents worked independently without micromanagement
5. **Structured Communication:** ActionResponse format enabled clean data transfer

---

This example demonstrates the power of multi-agent orchestration for complex, multi-step tasks that require different specialized capabilities.

