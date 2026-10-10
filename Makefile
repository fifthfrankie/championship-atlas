.PHONY: setup ingest replay build check serve e2e
PORT ?= 4173
setup:
	npm ci --prefix site
ingest:
	python3 -m atlas.cli ingest
	python3 -m atlas.cli backfill
replay:
	python3 -m atlas.cli replay
build: replay
	python3 -m atlas.cli export
	cd site && npx tsx src/build.ts
check:
	python3 -m unittest discover -s tests
	cd site && npx tsc --noEmit && npm test
serve:
	@test -d build/site || { echo "No built site. Run: make build"; exit 1; }
	@echo "Serving http://localhost:$(PORT)/"; python3 -m http.server $(PORT) --directory build/site
e2e: build
	cd site && npx tsx e2e/journey.ts
