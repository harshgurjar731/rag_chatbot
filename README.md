# RAG Chatbot

The **RAG Chatbot** is a scalable, modular Retrieval-Augmented Generation (RAG) system designed to build intelligent conversational agents. It leverages a microservices architecture to decouple the frontend, backend API, and heavy-lifting worker processes, ensuring high performance and reliability.

## 📖 Architecture

For a deep dive into the system architecture, including the Worker Pool pattern and Redis communication, please refer to the [Architecture Documentation](architecture.md).

### High-Level Components

*   **Frontend**: A modern React application (Vite + Shadcn UI) providing an intuitive chat interface.
*   **Backend**: A FastAPI-based API Gateway that orchestrates requests, manages users/bots, and handles feedback.
*   **Worker Pool**: A scalable service that manages isolated processes for each bot to handle RAG pipelines independently.
*   **Redis**: Acts as the communication backbone (Message Broker) and state store.
*   **ChromaDB**: The default Vector Database for storing document embeddings.
*   **Phoenix**: Provides end-to-end tracing and observability for LLM applications.
                     
## 🚀 Getting Started

### Prerequisites

*   [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed on your machine.
*   (Optional) Python 3.10+ for local development.

### Installation

1.  **Clone the Repository**
    ```bash
    git clone <repository_url>
    cd rag_chatbot
    ```

2.  **Environment Configuration**
    Create a `.env` file in the `rag_chatbot` root directory (or ensure the existing one is configured). Key variables include:

    ```env
    # LLM Keys
    OPENAI_API_KEY=sk-...
    GROQ_API_KEY=gsk_...
    NVIDIA_API_KEY=nvapi-...

    # Service Configuration
    REDIS_HOST=redis
    DB_HOST=db
    WORKER_POOL_SIZE=5
    ```

3.  **Run with Docker Compose**
    Build and start all services:
    ```bash
    docker-compose up -d --build
    ```

4.  **Access the Application**
    *   **Frontend**: [http://172.200.163.232:8080](http://172.200.163.232:8080)
    *   **Backend API Docs**: [http://172.200.163.232:8000/docs](http://172.200.163.232:8000/docs)
    *   **Phoenix (Tracing)**: [http://172.200.163.232:6006](http://172.200.163.232:6006)

## 🛠️ Services Overview

| Service | Container Name | Description | Port |
| :--- | :--- | :--- | :--- |
| **Frontend** | `rag_frontend` | User Interface (React/Vite). | 8080 |
| **Backend** | `rag_backend` | API Gateway (FastAPI). | 8000 |
| **Worker Pool** | `worker-pool` | Manages RAG Bot processes. | - |
| **Redis** | `redis` | Message broker & cache. | 6379 |
| **PostgreSQL** | `db` | Application database. | 5432 |
| **ChromaDB** | `chromadb` | Vector database. | 8001 |
| **Phoenix** | `phoenix` | LLM Tracing & Observability. | 6006 |

## 📦 Features

*   **Scalable Worker Pool**: Bots run in isolated processes; if one crashes, others remain mostly unaffected.
*   **Real-time Streaming**: Responses are streamed to the frontend via Redis Pub/Sub.
*   **Multi-Model Support**: Configurable to use OpenAI, Groq, Nvidia, etc.
*   **Observability**: Full integration with Arize Phoenix for tracing RAG pipelines and gathering user feedback.
*   **Modular Design**: Easy to swap out vector stores or LLM providers.

