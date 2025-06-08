# Flexr Crew

Welcome to the Flexr Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

## Installation

Ensure you have Python >=3.10 <3.13 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

**Recommend using conda to avoid python env/venv issues**
> [Installing Miniconda](https://docs.anaconda.com/miniconda/install/#quick-command-line-install)
**Note: conda will default install python 3.13, install 3.12 and select it**


First, if you haven't already, install uv:

```bash
pip install uv
```

## TLDR (simple running)

1. Use uv to manage dependencies, uv sync will create venv and activate it, it also installs all dependencies from pyproject.yaml and uv.lock
```
uv sync 
```
2. Copy .env and modify the USER VARIABLES in `.env` file
```
cp .env.example .env
```
- config databse by editing `db_config.ini`, you need to init database by running 
```
psql -h $HOST -p $PORT -U $USER -f docs/sql/pg_init.sql
```
### Customizing

**Add your `OPENAI_API_KEY` into the `.env` file**

- Modify `src/flexr/config/agents.yaml` to define your agents
- Modify `src/flexr/config/tasks.yaml` to define your tasks
- Modify `src/flexr/crew.py` to add your own logic, tools and specific args
- Modify `src/flexr/main.py` to add custom inputs for your agents and tasks

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
$ crewai run
```

This command initializes the flexr Crew, assembling the agents and assigning them tasks as defined in your configuration.

### Running FastAPI

To run the FastAPI application, use the following command:

```
uvicorn app.main:app --reload
```

This will start the FastAPI server, which can be accessed at `http://127.0.0.1:8000`.
Swagger UI can be accessed at `http://127.0.0.1:8000/docs`.

## Understanding Your Crew

The flexr Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback regarding the Flexr Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
