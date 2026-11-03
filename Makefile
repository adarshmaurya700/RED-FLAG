.PHONY: demo native test build stop
demo:
	docker compose up --build
native:
	sh ./run_demo.sh --native
test:
	cd backend && uv run --with-requirements requirements.lock pytest
	npm run typecheck
build:
	npm run build
stop:
	docker compose down
