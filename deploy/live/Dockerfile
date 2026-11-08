# Deploy only after approval; secret-free offline build tests are allowed.
# Supply an approved, already-present immutable Python image digest.
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY crashcart/ /app/crashcart/
COPY migrations/ /app/migrations/
COPY web/index.html web/app.js web/style.css web/marketing.js /app/web/
COPY LICENSE /app/LICENSE
USER 10001:10001
ENTRYPOINT ["python", "-m", "crashcart.hosted_live"]
CMD ["api"]
