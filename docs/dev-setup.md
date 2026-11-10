# Developer setup: Python virtual environment

A virtual environment (`.venv/`) keeps this project's packages separate from the rest of your computer. Git ignores it.

## 1. Pick a Python version
Use **Python 3.13**, the version the Docker images will use, so your laptop and the containers behave the same.

```bash
python3.13 --version          # on macOS, installed at /Library/Frameworks/Python.framework/Versions/3.13
```

Python 3.14 also works, but 3.13 is the safer match for Docker.

## 2. Create and activate the environment (once)

```bash
cd smart-vitals
python3.13 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Your prompt now starts with `(.venv)`. Activate it again with `source .venv/bin/activate` each time you open a new terminal. Leave it with `deactivate`.

## 3. Secrets

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste the result into SECRET_KEY
```

Never commit `.env`.

## 4. Everyday commands

```bash
pytest                         # run the tests (the model tests are skipped until notebook 01 has saved a model)
ruff check .                   # lint
ruff check . --fix             # fix what can be fixed automatically
ruff format .                  # format the code
jupyter notebook notebooks/    # open the notebooks with the .venv kernel
```

## 5. If something goes wrong
- `command not found: pytest`: the environment is not active. Run `source .venv/bin/activate`.
- A package will not install: check `python --version` inside `.venv`, then delete `.venv` and repeat step 2.
- Jupyter uses the wrong Python: run `python -m ipykernel install --user --name smart-vitals`, then pick the **smart-vitals** kernel.

## The dashboard (Node.js)

Use Node 22 or 24 (LTS); Node 25 works but some test tools warn about it.

```bash
cd dashboard
npm install
npm run dev     # http://localhost:5173 (the API must be running on port 8000)
npm test
```

## Docker (the whole system)

Install Docker Desktop and start it. If `docker` is "command not found", tick *Settings, Advanced, System* (install the command-line tools), or use `/Applications/Docker.app/Contents/Resources/bin/docker`.

```bash
cp .env.example .env        # fill in every secret; generate each with:
python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up --build                 # dashboard http://localhost:8080, API http://localhost:8000/docs
docker compose --profile demo up --build  # ... plus the simulator streaming 30 patients over MQTT
docker compose down          # stop (add -v to delete the database and broker data too)
```
