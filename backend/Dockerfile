FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The project is uv/pyproject-managed; there has never been a requirements.txt.
COPY pyproject.toml uv.lock README.md ./
COPY ./src ./src
RUN pip install --no-cache-dir --prefix=/install .

# Everything both final stages share: the interpreter, the installed distribution, and a user
# that is not root. Splitting it out keeps `dev` and `runner` from drifting apart in the parts
# that are not supposed to differ between them.
FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system appgroup && adduser --system appuser

COPY --from=builder /install /usr/local

EXPOSE 8000

# The development image, and the one docker-compose.yaml builds.
#
# `PYTHONPATH=/app/src` is what makes the bind mount matter. Without it the process imports the
# copy of the code that `pip install` put in site-packages, and editing a file on the host would
# change nothing that is running — which is what the old `./src:/src` mount did, silently.
# PYTHONPATH is searched before site-packages, so the mounted source wins.
#
# `scripts/` is copied in rather than left on the host because there are no migrations in this
# repository: `scripts/seed.py` is the only code that creates the schema, so a fresh `pgdata`
# volume needs it once before any route can answer.
#
#     docker compose run --rm backend python scripts/seed.py --reset
#
# It is mounted over in docker-compose.yaml as well, so an edit to the seeder needs no rebuild.
FROM base AS dev

COPY ./src ./src
COPY ./scripts ./scripts

ENV PYTHONPATH=/app/src

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/src"]

# The production image: no source on disk beyond the installed distribution, no reloader.
FROM base AS runner

USER appuser

# `main:app`, not `src.main:app`: the wheel installs the seven context packages plus the two
# flat modules at the top level, so the composition root is importable as `main`. Inside `src/`
# every module already imports `billing.…` rather than `src.billing.…`, which is the same
# layout the editable install gives a developer.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
