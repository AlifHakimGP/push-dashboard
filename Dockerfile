# ---- Stage 1: build the React frontend ----
# This stage exists only to run `npm install` + `npm run build`. Its output
# (frontend/dist/) gets copied into the final image below; the Node.js
# toolchain itself, node_modules, and all the JS source never make it into
# the image you actually run. This keeps the final image small and means
# the production container has no Node.js installed at all.
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the actual runtime image ----
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
# Pull in ONLY the built static files from stage 1 — not the source, not
# node_modules. `--from=frontend-build` is what makes this a genuine
# multi-stage build rather than just two separate images.
COPY --from=frontend-build /frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
