# TalentBridge AI — Employer Outreach Program Agent

### Agentic AI Bootcamp — Final Production Framework (SDA / WeCloudData)

## Overview

TalentBridge AI is a production-ready multi-agent recruitment platform that automates employer outreach, candidate matching, and HR workflows using Large Language Models (LLMs). The platform leverages LangGraph, LangChain, FastAPI, PostgreSQL, and Retrieval-Augmented Generation (RAG) to build scalable AI-driven recruitment workflows.

### Project Team
- Abdulmohsen Alghamdi
- Osama Alhazmi
- Abdullah Aljaber

##  Repository Architecture Overview
This workspace implements a robust, completely decoupled multi-agent engine using LangGraph, FastAPI, and Streamlit.

```text
talentbridge-ai/
├── data/          ← Cleaned datasets, compliance playbooks, and outreach templates
├── database/      ← PostgreSQL relational system blueprints and seed records
├── shared/        ← Data schemas, configuration instances, and core LLM wrappers
├── rag/           ← Semantics-based embeddings and knowledge retrieval indices
├── agents/        ← Specialized Python logic routines for all 12 system agents
├── tools/         ← External system connectivity engines (Search, Email, APIs)
├── graph/         ← LangGraph pipeline engine and background runtime task schedulers
├── api/           ← Unified FastAPI server application routes
├── frontend/      ← Streamlit interactive client-side application interface
└── tests/         ← Quality-assurance end-to-end multi-agent validation scripts
