# TalentBridge AI

### Multi-Agent Recruitment Platform

**Agentic AI Bootcamp – Final Capstone Project (Saudi Digital Academy & WeCloudData)**

---

## Overview

TalentBridge AI is a capstone multi-agent recruitment platform designed to automate employer outreach, candidate matching, and HR workflows using Large Language Models (LLMs).

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

## Key Features

- Multi-Agent architecture powered by LangGraph
- Intelligent employer outreach automation
- AI-powered candidate matching
- Retrieval-Augmented Generation (RAG)
- Human-in-the-Loop (HITL) validation
- FastAPI backend services
- PostgreSQL database integration
- Streamlit interactive user interface

---

## Repository Architecture Overview

This repository implements a modular multi-agent platform built with LangGraph, FastAPI, and Streamlit.

```text
talentbridge-ai/
├── data/          ← Cleaned datasets, compliance playbooks, and outreach templates
├── database/      ← PostgreSQL relational system blueprints and seed records
├── shared/        ← Data schemas, configuration instances, and core LLM wrappers
├── rag/           ← Semantic embeddings and knowledge retrieval indices
├── agents/        ← Specialized Python logic for all 12 AI agents
├── tools/         ← External integrations (Search, Email, APIs)
├── graph/         ← LangGraph workflow orchestration and background schedulers
├── api/           ← FastAPI backend services
├── frontend/      ← Streamlit user interface
└── tests/         ← End-to-end validation and testing
```

---

## Core Technologies

- Python
- LangGraph
- LangChain
- FastAPI
- PostgreSQL
- Streamlit
- OpenAI API
- Retrieval-Augmented Generation (RAG)
