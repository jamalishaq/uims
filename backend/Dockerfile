FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The project is uv/pyproject-managed; there has never been a requirements.txt.
COPY pyproject.toml uv.lock README.md ./
COPY ./src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runner

WORKDIR /app

RUN addgroup --system appgroup && adduser --system appuser

COPY --from=builder /install /usr/local

USER appuser

EXPOSE 8000

# `main:app`, not `src.main:app`: the wheel installs the seven context packages plus the two
# flat modules at the top level, so the composition root is importable as `main`. Inside `src/`
# every module already imports `billing.…` rather than `src.billing.…`, which is the same
# layout the editable install gives a developer.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]