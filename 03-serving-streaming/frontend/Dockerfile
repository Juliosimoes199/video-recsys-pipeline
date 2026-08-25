# --- build ---
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_CLERK_PUBLISHABLE_KEY
ARG VITE_API_URL=/api
ARG VITE_UPLOAD_ENABLED=true
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_UPLOAD_ENABLED=$VITE_UPLOAD_ENABLED

RUN npm run build

# --- serve ---
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
