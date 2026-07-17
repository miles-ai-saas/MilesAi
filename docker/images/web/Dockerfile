FROM node:20-alpine AS builder
WORKDIR /app
COPY ui/workbench/package.json ui/workbench/package-lock.json* ./
RUN npm install
COPY ui/workbench .
RUN npm run build

FROM nginx:alpine
COPY docker/images/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/out /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
