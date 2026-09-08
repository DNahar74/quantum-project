FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --legacy-peer-deps

COPY frontend/ .
RUN npm run build

FROM nginx:alpine

# Non-root user setup for nginx
RUN addgroup -S appuser && adduser -S appuser -G appuser && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appuser /var/run/nginx.pid && \
    chown -R appuser:appuser /var/cache/nginx && \
    chown -R appuser:appuser /usr/share/nginx/html

COPY --from=builder --chown=appuser:appuser /app/dist /usr/share/nginx/html

# Custom nginx config to listen on 8080 and support SPA routing
RUN echo 'server { \
    listen 8080; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

USER appuser

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
