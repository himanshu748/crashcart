# Deploy only after approval; secret-free offline build tests are allowed.
# Supply an approved, already-present immutable Python image digest.
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY crashcart/ /app/crashcart/
COPY migrations/ /app/migrations/
COPY web/index.html web/app.js web/style.css web/marketing.js /app/web/
COPY web/judge/index.html web/judge/product.html web/judge/integrations.html web/judge/demo.html web/judge/app.js web/judge/style.css web/judge/site.js /app/web/judge/
COPY evidence/runs/paypal-live/early-response-loss-input.json /app/evidence/runs/paypal-live/early-response-loss-input.json
COPY evidence/runs/submission-ready/ai-historical-summary.json /app/evidence/runs/submission-ready/ai-historical-summary.json
COPY LICENSE /app/LICENSE
USER 10001:10001
ENTRYPOINT ["python", "-m", "crashcart.hosted_live"]
CMD ["api"]
