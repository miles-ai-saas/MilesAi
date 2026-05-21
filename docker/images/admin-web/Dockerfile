FROM node:20-alpine AS builder
WORKDIR /app
COPY admin_frontend/package.json admin_frontend/package-lock.json* ./
RUN npm install
COPY admin_frontend .
ARG NEXT_PUBLIC_ADMIN_API_URL=http://localhost:8000/api/admin/v1
ARG NEXT_PUBLIC_TENANT_WEB_URL=http://localhost:3000
ENV NEXT_PUBLIC_ADMIN_API_URL=$NEXT_PUBLIC_ADMIN_API_URL
ENV NEXT_PUBLIC_TENANT_WEB_URL=$NEXT_PUBLIC_TENANT_WEB_URL
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3001
ENV PORT=3001
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
