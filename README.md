# HOUSIA

A rental platform where the landlord's side runs by itself. HOUSIA reads messages from a
portal inbox (Idealista, or a built-in mock portal), answers them, and takes each candidate
through application, documents, ranking, viewing, waiting list, final choice and contract.

- What to build and why: [PLAN.md](PLAN.md)
- Technical contract (files, schema, signatures, routes): [DESIGN.md](DESIGN.md)

## Setup

Needs [uv](https://docs.astral.sh/uv/). Python 3.12 is installed by uv.

```bash
uv sync
cp .env.example .env      # optional; edit values as needed
```

## Run the web app

```bash
uv run python run.py      # http://localhost:5000
```

Use another port and database per worktree, for example
`PORT=5004 HOUSIA_DB=instance/b4.db uv run python run.py`.

## Run the worker

The worker reads portal messages, writes replies and sends approved ones.

```bash
uv run python -m housia.worker          # loop
uv run python -m housia.worker --once   # one pass
```

The channel is set by `CHANNEL` (`mock` by default).

## Run the tests

```bash
uv run pytest
```

## Reset the demo

Open `/demo` and press "Reset", or send `POST /demo/reset`. This drops the database and loads
the seed data again.
