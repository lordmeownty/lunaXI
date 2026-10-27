.PHONY: setup api web test eval data agents deploy open-football-bootstrap open-football-fictional-db
setup:  ; pip install -r backend/requirements.txt && cd frontend && npm install
agents: ; pip install --pre -r backend/requirements-agents.txt
api:    ; cd backend && uvicorn app.main:app --reload --port 8000
web:    ; cd frontend && npm run dev
test:   ; cd backend && python -m pytest -q
eval:   ; python evaluation/run_eval.py --inprocess --min-pass-rate 0.95
data:   ; python data/generator/generate_matches.py
deploy: ; ./infra/deploy.sh
open-football-bootstrap:    ; ./services/simulator-adapter/bootstrap_open_football.sh
open-football-fictional-db: ; python services/simulator-adapter/openfootball_adapter.py export-db
