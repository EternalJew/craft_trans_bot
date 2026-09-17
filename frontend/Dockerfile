FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
RUN apk add --no-cache apache2-utils   # htpasswd, for the basic auth on /admin/
COPY --from=build /app/dist /usr/share/nginx/html/admin
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY admin-auth.sh /docker-entrypoint.d/40-admin-auth.sh
RUN chmod +x /docker-entrypoint.d/40-admin-auth.sh && touch /etc/nginx/admin-auth.conf
EXPOSE 80
