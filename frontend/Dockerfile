# Build statico servito da nginx: in produzione il frontend è HTML e JS, non
# un dev server. Il proxy /api verso il backend è lo stesso meccanismo del
# proxy Vite in sviluppo, così le due modalità si comportano allo stesso modo.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Il dev server resta disponibile come target separato per lo sviluppo locale.
FROM node:22-slim AS dev
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
