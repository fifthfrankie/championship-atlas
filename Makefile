.PHONY: setup ingest replay build check serve
setup:
	npm ci --prefix site
ingest:
	python3 -m atlas.cli ingest
replay:
	python3 -m atlas.cli replay
build: replay
	@echo "site build: not implemented yet" && exit 1
check:
	python3 -m unittest discover -s tests
serve:
	@echo "serve: not implemented yet" && exit 1
