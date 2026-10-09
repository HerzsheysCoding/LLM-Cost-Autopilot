LLM Cost Autopilot Gateway

[![Build Status](https://github.com/yourusername/llm-autopilot/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/llm-autopilot/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Redis Stack](https://img.shields.io/badge/Redis-Stack-red.svg)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade LLM FinOps gateway designed to drastically reduce OpenAI/Anthropic API costs through **RediSearch vector semantic caching**, **dynamic model cascading**, and **atomic Lua budget enforcement**.

## Architecture Core
1. **Semantic Vector Cache (RediSearch HNSW):** Intercepts queries before they hit upstream LLMs. If a user asks a question with $\ge$ 92% semantic similarity to a past query, the gateway returns the cached response in $<10ms$ for **$0.00**.
2. **Cost-Cascading Router:** Automatically calculates `tiktoken` metrics and payload complexity. Routes simple/short tasks to `gpt-4o-mini` and heavy architectural tasks to `gpt-4o`.
3. **Atomic FinOps Guardrails:** Uses Redis Lua scripts to safely enforce hard daily organizational token budgets across concurrent asynchronous workers.

## Prerequisites
- Python 3.11+
- Redis Stack (Must be the `redis-stack` or `redis-stack-server` image to support the RediSearch module `FT.SEARCH`)
- OpenAI API Key

## Quickstart (Local Docker Compose)

1. **Clone & Configure:**
   ```bash
   git clone [https://github.com/yourusername/llm-autopilot.git](https://github.com/yourusername/llm-autopilot.git)
   cd llm-autopilot
   echo "OPENAI_API_KEY=sk-your-key-here" > .env
