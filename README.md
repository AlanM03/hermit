# Hermit CLI — Local-First AI Developer Assistant

![Hermit CLI screenshot](./assets/hermit-cli.png)

Hermit CLI is a privacy-focused, local-first AI assistant being built in Python using FastAPI and Typer. It supports running any local language model (LLM) for offline, context-aware question answering and code interactions.

## Project Status

Hermit CLI is currently under active development. The core CLI functionality is operational, with support for Ollama and LM Studio models. A GUI is planned and will be added after the initial CLI launch.

---

## Key Features

- End-to-end Retrieval-Augmented Generation (RAG) pipeline that:
  - Ingests code and documents
  - Generates vector embeddings for semantic search
  - Queries an offline ChromaDB vector store
  - Executes subprocesses for enhanced code interaction
- Stateful chat system engineered for privacy:
  - Persistent, encrypted `.jsonl` chat history storage locally
  - Custom auto-compaction pipeline using token counting and summarization API to prevent context window overflow powered by [LocalGrid](https://pypi.org/project/localgrid/)
- Built with FastAPI for backend API and Typer for smooth CLI experience
- Compatible with any local language model to ensure full offline functionality

---

## Model Compatibility and GPU Usage

Currently, Hermit CLI supports only models running on Ollama and LM Studio platforms through their respective model registries.

- You must enable GPU usage manually on these platforms for optimal performance.
- For **Ollama**, GPU acceleration can be enabled via configuration or command-line flags as detailed in the [Ollama documentation](https://ollama.com/docs) and [Ollama Hardware Support](https://docs.ollama.com/gpu).
- For **LM Studio**, GPU support is built-in but may require driver and environment setup.

> Important:  
> On **AMD graphics cards series 7000 and above**, Vulkan API is required for GPU acceleration.  
> This often necessitates installing Vulkan drivers and configuring the platform to use Vulkan as the GPU backend.

## Architecture Overview

Hermit CLI emphasizes local execution and user data privacy. Core modules include:

- **Ingestion & Embedding**: Capture and embed developer codebases for enhanced semantic retrieval
- **ChromaDB Offline Store**: Efficiently store and query vector embeddings
- **Subprocess Executor**: Securely run code snippets and commands contextually
- **Stateful Chat Manager**: Maintain persistent context with auto-summarization of chat logs to avoid token limits

---

### Usage Example

Ask Hermit a question using the `ponder` command.

```bash
❯ hermit ponder "Does a tower truly exist if its only occupant is a sorcerer who never leaves?"

Starting thought...

"Does the tower hold sway over the sorcerer's essence, or does the sorcerer's mere presence animate the tower into being,
and thus do we ponder: Is it the tower that exists, or is it merely the sorcerer's own echo?"
```

## Contributing

Contributions are welcome once version **0.1.0** releases! Please open issues and submit pull requests to improve features, add support for new models, or fix bugs.

---

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.