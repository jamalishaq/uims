# Dependencies, in their own stage so that a source change does not reinstall them. Only the
# two manifests are copied here: Docker rebuilds this layer when they change and reuses it when
# any other file does.
FROM node:20-alpine AS deps

WORKDIR /app

# `npm ci` rather than `npm install`: it installs exactly what package-lock.json pins and fails
# if the lockfile and package.json disagree, which is the behaviour an image wants. `npm
# install` would happily resolve something newer and bake a build nobody can reproduce.
COPY package.json package-lock.json ./
RUN npm ci

# The development image, and the one docker-compose.yaml builds: Vite's dev server, with the
# source bind-mounted over this copy so a save on the host triggers HMR.
FROM deps AS dev

WORKDIR /app

COPY . .

EXPOSE 5173

# `--host 0.0.0.0` is not optional here. Vite binds to localhost by default, which inside a
# container means the container's own loopback — the published port would accept a connection
# and find nothing listening on it.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
