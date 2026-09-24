# Support Ticket AI

This project is a small AI system for analysing customer support tickets. It reads the provided CSV file, answers questions about the tickets, and reports possible anomalies.

It includes:

- A FastAPI REST API
- A simple Streamlit interface
- Ollama support for local LLM-based question understanding
- An offline fallback for testing without an LLM
- Automated tests

## Run With Docker

The easiest way to run both the API and the UI is:

```bash
docker compose up --build
```

Open these URLs:

- UI: http://localhost:8501
- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

For LLM responses, install Ollama and download the model:

```bash
ollama pull llama3.2
```

The application still works if Ollama is not running. In that case, it uses the calculated results directly.

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Start the UI in another terminal:

```bash
streamlit run streamlit_app.py
```

For a local test without Ollama, run either command with `LLM_PROVIDER=none`.

## Example Questions

The system can answer questions such as:

- How many tickets are currently open?
- Which agent resolved the most tickets this month?
- Show me all Critical tickets not resolved within 12 hours.
- What is the average customer rating for Technical category tickets?
- Are there any anomalies in resolution times this week?

With the included dataset, some results are:

- Open tickets: `111`
- Top agent this month: `AGT-01` with `16` resolved tickets
- Technical ticket rating: `3.74`

## API Endpoints

- `GET /health` checks that the service is running.
- `GET /api/tickets` returns ticket records.
- `POST /api/query` accepts a natural-language question.
- `POST /api/anomalies` detects unusual ticket activity.

Example query:

```bash
curl -X POST http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many tickets are currently open?"}'
```

## Project Structure

```text
app/
  api/       API routes
  data/      CSV loading and validation
  models/    Request and response models
  services/  Query, LLM, and anomaly logic
data/        support ticket CSV
tests/       automated tests
streamlit_app.py
```

The analytics are calculated from the CSV first. The LLM is only used to understand the question and optionally phrase the final answer, so it cannot invent ticket counts or anomaly records.

## Tests

```bash
pytest -q
```

## Limitations

The question parser is designed for common support-ticket questions, not arbitrary SQL. The phrases `this week` and `this month` are calculated relative to the latest date in the provided dataset. The anomaly rules are suitable for this prototype but would need stronger monitoring and alerting in production.
