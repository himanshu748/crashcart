FROM python:3.13-slim AS export
WORKDIR /src
COPY crashcart/ crashcart/
COPY migrations/ migrations/
COPY web/judge/ web/judge/
COPY evidence/runs/paypal-live/early-response-loss-input.json evidence/runs/paypal-live/early-response-loss-input.json
COPY LICENSE LICENSE
RUN python -m crashcart.judge --export-site /site

FROM caddy:2-alpine
COPY --from=export /site /srv
COPY deploy/judge/Caddyfile /etc/caddy/Caddyfile
# Runtime contains exported review assets only; no Python, provider adapters or .env.
EXPOSE 80 443
