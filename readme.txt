# TalentBridge AI
### Multi-Agent Recruitment Platform

### Agentic AI Bootcamp — Final Production Framework (SDA / WeCloudData)

## Overview

TalentBridge AI is a production-ready multi-agent recruitment platform designed to automate employer outreach, candidate matching, and HR workflows using Large Language Models (LLMs).

The platform leverages LangGraph, LangChain, FastAPI, PostgreSQL, and Retrieval-Augmented Generation (RAG) to build scalable AI-driven recruitment workflows through a modular multi-agent architecture.

---

## Project Team

- Abdulmohsen Alghamdi
- Osama Alhazmi
- Abdullah Aljaber

---

## Technology Stack

### AI & LLM Frameworks
- LangGraph
- LangChain
- OpenAI API
- Retrieval-Augmented Generation (RAG)

## Key Features

- Multi-Agent Architecture powered by LangGraph
- Intelligent employer outreach automation
- AI-powered candidate matching
- Retrieval-Augmented Generation (RAG)
- Human-in-the-Loop (HITL) validation
- FastAPI backend services
- PostgreSQL database integration
- Streamlit interactive interface

### Backend
- Python
- FastAPI
- PostgreSQL

### Frontend
- Streamlit

### AI Concepts
- Multi-Agent Systems
- Human-in-the-Loop (HITL)
- Vector Databases
- Prompt Engineering

---

## Repository Architecture Overview

This repository implements a production-ready, modular multi-agent platform using LangGraph, FastAPI, and Streamlit.

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
```
