FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev

COPY server.js ./
COPY public ./public
COPY data ./data

ENV PORT=8080
EXPOSE 8080

CMD ["node", "server.js"]
