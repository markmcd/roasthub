# GitHubRoast - Gemini API x CrewAI Demo App

Welcome to the GithubRoast project, powered by the [Gemini API](https://ai.google.dev/gemini-api/) and [crewAI](https://crewai.com). This app shows how to set up a CrewAI crew using Gemini models grounded with Google Search.

If you just want to try it out, go to https://roast.markm.cd/

## How it works

A CrewAI crew is defined that follows a short plan:

* Research the user
* Research their projects
* Write a roast

You can see the CrewAI configuration in [the config
dir](src/github_roaster/config/). Also check out the [custom LLM
class](src/github_roaster/crew.py) that uses the `google_search` tool inside
CrewAI.

The agents all use the Gemini API, by default [Gemini 2.5
Flash](https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash-preview).
The agents defined for the research tasks use the Gemini API's [Google Search
Grounding](https://ai.google.dev/gemini-api/docs/grounding) feature to look up
any relevant information on the supplied user's GitHub profile. This is easy to
implement, runs pretty quickly and can grab any relevant GitHub information from
around the web.

The Crew is wrapped in a FastAPI that serves a streaming endpoint. This API
streams progress updates to indicate as tasks complete, and eventually returns a
message with the roast, in markdown.

The web frontend is just a static HTML page that calls the API and renders
updates. If you want to develop something more complex, the API is serving the
HTML as a static route, so you can deploy a separate web app pointed at the API.

## Installation

Ensure you have Python >=3.10 <3.13 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling.

### Initial setup

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

```bash
uv sync
```

#### API key

Grab an API key from [Google AI Studio](https://aistudio.google.com/apikey) and
add it to the `.env` file as `GEMINI_API_KEY`.

```bash
cp .env.example .env
# Now edit .env and add add your key to the GEMINI_API_KEY line.
```

You can now choose to run the API service locally or with Docker. Read one of
the the next two sections depending on what you prefer. Docker will need to be
installed, or just run locally using the already-installed tools.

### Run locally

Run the service. Use `--reload` to automatically refresh while you're editing.

```bash
uv run uvicorn api.service:app --reload
```

With the API server running, browse to http://localhost:8000/

### Docker

To build and run a docker image locally, using a specified API key:

```bash
docker build -t roaster-backend-local:latest .
docker run -p 8000:8080 -e GEMINI_API_KEY=your_api_key_here --name my-roaster-app-local roaster-backend-local:latest
```

With the API server running, browse to the docker port, http://localhost:8080/

## Running the Crew

To run your crew of AI agents directly, without an API server, run this from the root folder of your project. Pass your GitHub username as the last argument to roast yourself.

```bash
uv run github_roaster yourgithubusername
```

You will get a markdown file created in the same directory, `yourgithubusername.md`. Load it in your favourite markdown renderer, e.g. [`glow`](https://github.com/charmbracelet/glow).

