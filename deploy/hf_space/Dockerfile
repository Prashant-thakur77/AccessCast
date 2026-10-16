# AccessCast proof API on a free Hugging Face Space (CPU). Serves POST /api/attack for the live site's proof page.
# The Token Factory key comes from Space secrets (AMD_TF_API_KEY, AMD_TF_BASE_URL); it never reaches the browser.
FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.9.5
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev && useradd -m app && chown -R app /app
USER app
ENV ACCESSCAST_WORKER_MODE=real ACCESSCAST_PROOF_ORIGINS=https://accesscast.vercel.app \
    ACCESSCAST_PROJECTS_DIR=/tmp/projects PATH=/app/.venv/bin:$PATH
EXPOSE 7860
CMD ["uvicorn", "accesscast.proof.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860"]
