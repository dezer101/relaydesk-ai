# RelayDesk — Support Operations Copilot

RelayDesk is a small AI workflow prototype I built around a familiar support problem: turning an incoming request into a clear, evidence-backed next step without letting automation take action on its own.

The demo uses fictional customer tickets and a fictional support handbook. It classifies each ticket, retrieves relevant handbook passages, drafts a response, and proposes one next action. A person can review the sources and edit the response before approving a simulated action. Approved actions are recorded in a local audit view; they do not contact a real customer system.

## Run it locally

Use Python 3.10 or newer.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py app.py
```

Open `http://127.0.0.1:5055` in a browser. On macOS or Linux, activate the environment with `source .venv/bin/activate` and start the app with `python app.py`.

## Try the demo

1. Choose a sample request from the triage queue.
2. Review its category, priority and suggested action.
3. Expand the handbook matches to read the exact supporting guidance.
4. Edit the draft reply if needed.
5. Approve the suggested action to record it in the local activity log.
6. Open **Activity log** to see the triage run and the approval event.

The approval is deliberately a local demo record. This app has no connection to an external ticketing, billing or customer system.

## What I wanted to practise

- Designing a multi-step AI workflow around a user-facing support problem.
- Retrieving and showing source passages so a person can check the recommendation.
- Separating recommendations from actions with a human approval step.
- Keeping a small audit trail of triage and approval events.
- Providing a useful local demo that does not require a model key.
- Keeping optional model credentials on the server rather than in browser code.

## Optional model-written draft

By default, draft replies are generated from the retrieved handbook text with a local fallback. To try an optional model-written draft, copy `.env.example` to `.env` and set `OPENAI_API_KEY` and a supported `OPENAI_MODEL`. Flask reads those values when the server starts. The key is read only by Flask and `.env` is ignored by Git. Never put a key in the browser or commit it.

The model is asked to use only retrieved evidence and avoid promising outcomes. The app still displays its source material, and the proposed action still requires a human click. A model response should be reviewed before use.

## Project structure

```text
relaydesk-ai/
├── app.py                 # Flask routes, retrieval, triage and approval gate
├── data/
│   ├── knowledge.json     # Fictional support handbook
│   └── tickets.json       # Fictional demo tickets
├── static/                # Browser interface and styles
└── templates/index.html   # App shell
```

## Scope

This is a learning prototype with a small synthetic dataset and a simple retrieval and classification approach. The optional model path is not a production integration. Approved actions are simulated and stored in process memory, so they clear when the server restarts. The app does not authenticate users, persist records to a database, or connect to a live service desk.

