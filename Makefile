.PHONY: setup ingest replay build check serve e2e
PORT ?= 4173
setup:
	npm ci --prefix site
ingest:
	python3 -m atlas.cli ingest
replay:
	python3 -m atlas.cli replay
build: replay
	python3 -m atlas.cli export
	cd site && npx tsx src/build.ts
# The count guards exist because an emptied test file still "passes". Raise the minimums when tests are added.
check:
	@mkdir -p build
	python3 -m unittest discover -s tests 2>&1 | tee build/py-test.log
	@grep -qE '^Ran (7[1-9]|[8-9][0-9]|[1-9][0-9]{2,}) tests' build/py-test.log || { echo "too few Python tests ran"; exit 1; }
	@! grep -qE '^(FAILED|ERROR)' build/py-test.log || { echo "Python tests failed"; exit 1; }
	cd site && npx tsc --noEmit
	cd site && npm test 2>&1 | tee ../build/node-test.log
	@grep -qE '^# tests (9|[1-9][0-9]+)$$' build/node-test.log || { echo "too few site tests ran"; exit 1; }
	@grep -qE '^# fail 0$$' build/node-test.log || { echo "site tests failed"; exit 1; }
serve:
	@test -d build/site || { echo "No built site. Run: make build"; exit 1; }
	@echo "Serving http://localhost:$(PORT)/"; python3 -m http.server $(PORT) --directory build/site
e2e: build
	cd site && npx tsx e2e/journey.ts
