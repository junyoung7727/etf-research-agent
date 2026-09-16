FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY original ./original
COPY public ./public
COPY src ./src
COPY tools/build-original.mjs ./tools/build-original.mjs
COPY index.html original.html tsconfig.json vite.config.ts playwright.config.ts ./
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EDGE_MODE=demo PORT=8018
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-provider.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-provider.txt
RUN useradd --create-home --uid 10001 edge && mkdir /app/data && chown edge:edge /app/data
COPY --from=web /build/dist ./dist
COPY --from=web /build/public ./public
COPY server ./server
ENV KIWOOM_MCP_COMMAND=kiwoom-exec-mcp KIWOOM_MCP_ARGS=[]
USER edge
EXPOSE 8018
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8018')+'/api/health',timeout=3)"
CMD ["python", "-m", "server.start"]
