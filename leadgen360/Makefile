.PHONY: up down collect collect-dry collect-linkedin collect-boamp collect-malt collect-ted train demo test status logs

up:
	docker-compose up -d
	@echo ""
	@echo "Services démarrés :"
	@echo "  n8n:      http://localhost:5678  (admin / admin123)"
	@echo "  Metabase: http://localhost:3000"
	@echo "  API:      http://localhost:8000/docs"
	@echo "  Redis:    localhost:6379"

down:
	docker-compose down

# ── Collecte complète (LinkedIn + BOAMP + TED + Malt) ────────────────────────
collect:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all

collect-dry:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --dry-run

# ── Collecteurs individuels ───────────────────────────────────────────────────
collect-linkedin-b2b:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --source linkedin_b2b

collect-linkedin-b2b-dry:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --dry-run --source linkedin_b2b

collect-linkedin:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --source linkedin

collect-linkedin-dry:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --dry-run --source linkedin

collect-cobol:
	LEADGEN_USE_TFIDF=1 python -m collectors.linkedin_hiring --tech COBOL --limit 10

collect-boamp:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --source boamp

collect-boamp-dry:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --dry-run --source boamp

collect-malt:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --source malt

collect-ted:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --source ted

collect-ted-dry:
	LEADGEN_USE_TFIDF=1 python -m collectors.run_all --dry-run --source ted

train:
	LEADGEN_USE_TFIDF=1 python -m nlp.trainer

demo:
	@echo "Déclenchement du workflow de démo..."
	curl -s -X POST http://localhost:5678/webhook/demo \
	  -H "Content-Type: application/json" \
	  -d '{"technology": "COBOL", "location": "France"}' | python -m json.tool

test:
	pytest tests/ -v --tb=short

status:
	@echo "=== Santé API ==="
	curl -s http://localhost:8000/health | python -m json.tool
	@echo ""
	@echo "=== Services Docker ==="
	docker-compose ps

logs:
	docker-compose logs -f api

db-shell:
	docker-compose exec postgres psql -U $${POSTGRES_USER:-leadgen} -d $${POSTGRES_DB:-leadgen360}

db-stats:
	docker-compose exec postgres psql -U $${POSTGRES_USER:-leadgen} -d $${POSTGRES_DB:-leadgen360} \
	  -c "SELECT country, sector_label, count(*), round(avg(priority_score)) as avg_score FROM opportunities GROUP BY country, sector_label ORDER BY count DESC;"

clean-models:
	rm -f nlp/models/*.joblib

rebuild-api:
	docker-compose build api && docker-compose up -d api

trigger-collect:
	curl -s -X POST http://localhost:8000/api/collect/all \
	  -H "X-API-Key: leadgen360_demo_secret_2024" \
	  -H "Content-Type: application/json" | python -m json.tool

trigger-linkedin:
	curl -s -X POST http://localhost:8000/api/collect/linkedin \
	  -H "X-API-Key: leadgen360_demo_secret_2024" \
	  -H "Content-Type: application/json" | python -m json.tool
