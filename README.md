# BetAp

BetAp is a football match-analysis dashboard backed by three complementary models:

1. Independent Poisson score modeling
2. Form/strength logistic modeling
3. Gamma-Poisson Monte Carlo simulation (30,000 runs)

The ensemble estimates market probability, fair odds, expected value, model agreement, and a capped quarter-Kelly stake. It never describes a bet as guaranteed or safe.

## Run locally

```powershell
Copy-Item .env.example .env
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. API documentation is at `/api/docs`.

## Configuration

Set `FOOTYSTATS_API_KEY` in `.env`. Never commit `.env`.

## Deploy

The included Docker Compose service binds only to localhost. Nginx receives public traffic for `betap.cm-ea.com` and proxies it to the application.

> Betting involves risk. Model estimates are uncertain and do not guarantee returns.
