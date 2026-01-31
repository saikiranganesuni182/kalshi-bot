# Docker: From Beginner to Professional

A comprehensive guide to mastering Docker for software development and deployment.

---

## Table of Contents

1. [Introduction to Docker](#1-introduction-to-docker)
2. [Core Concepts](#2-core-concepts)
3. [Installation & Setup](#3-installation--setup)
4. [Basic Commands](#4-basic-commands)
5. [Working with Images](#5-working-with-images)
6. [Dockerfiles](#6-dockerfiles)
7. [Docker Volumes](#7-docker-volumes)
8. [Docker Networking](#8-docker-networking)
9. [Docker Compose](#9-docker-compose)
10. [Multi-Stage Builds](#10-multi-stage-builds)
11. [Best Practices](#11-best-practices)
12. [Production Deployment](#12-production-deployment)
13. [Debugging & Troubleshooting](#13-debugging--troubleshooting)
14. [Advanced Topics](#14-advanced-topics)

---

## 1. Introduction to Docker

### What is Docker?

Docker is a platform that enables you to package, distribute, and run applications in isolated environments called **containers**.

### The Problem Docker Solves

**Before Docker:**
```
Developer: "It works on my machine!"
Operations: "Well, it doesn't work on the server!"
```

**With Docker:**
- Same environment everywhere (dev, staging, production)
- No more "works on my machine" problems
- Easy to share and reproduce environments

### Containers vs Virtual Machines

```
┌─────────────────────────────────────────────────────────────┐
│                    VIRTUAL MACHINES                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                      │
│  │  App A  │  │  App B  │  │  App C  │                      │
│  ├─────────┤  ├─────────┤  ├─────────┤                      │
│  │ Bins/   │  │ Bins/   │  │ Bins/   │                      │
│  │ Libs    │  │ Libs    │  │ Libs    │                      │
│  ├─────────┤  ├─────────┤  ├─────────┤                      │
│  │ Guest   │  │ Guest   │  │ Guest   │  ← Full OS per VM    │
│  │ OS      │  │ OS      │  │ OS      │    (Heavy: GBs)      │
│  └─────────┘  └─────────┘  └─────────┘                      │
│  ┌─────────────────────────────────────┐                    │
│  │           Hypervisor                │                    │
│  └─────────────────────────────────────┘                    │
│  ┌─────────────────────────────────────┐                    │
│  │           Host OS                   │                    │
│  └─────────────────────────────────────┘                    │
│  ┌─────────────────────────────────────┐                    │
│  │           Infrastructure            │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      CONTAINERS                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                      │
│  │  App A  │  │  App B  │  │  App C  │                      │
│  ├─────────┤  ├─────────┤  ├─────────┤                      │
│  │ Bins/   │  │ Bins/   │  │ Bins/   │  ← Shared OS kernel  │
│  │ Libs    │  │ Libs    │  │ Libs    │    (Light: MBs)      │
│  └─────────┘  └─────────┘  └─────────┘                      │
│  ┌─────────────────────────────────────┐                    │
│  │         Docker Engine               │                    │
│  └─────────────────────────────────────┘                    │
│  ┌─────────────────────────────────────┐                    │
│  │           Host OS                   │                    │
│  └─────────────────────────────────────┘                    │
│  ┌─────────────────────────────────────┐                    │
│  │           Infrastructure            │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

| Feature | Containers | Virtual Machines |
|---------|------------|------------------|
| Startup Time | Seconds | Minutes |
| Size | MBs | GBs |
| Performance | Near native | Overhead |
| Isolation | Process level | Hardware level |
| OS | Shares host kernel | Full OS per VM |

---

## 2. Core Concepts

### Docker Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Docker Client                            │
│                   (docker CLI commands)                       │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      Docker Daemon                            │
│                       (dockerd)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │   Images    │  │  Containers │  │     Networks        │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │   Volumes   │  │   Plugins   │  │     Other...        │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Docker Registry                            │
│              (Docker Hub, ECR, GCR, etc.)                     │
└──────────────────────────────────────────────────────────────┘
```

### Key Terminology

| Term | Definition |
|------|------------|
| **Image** | A read-only template with instructions for creating a container. Think of it as a "class" in OOP. |
| **Container** | A runnable instance of an image. Think of it as an "object" (instance of a class). |
| **Dockerfile** | A text file with instructions to build an image. |
| **Registry** | A storage and distribution system for Docker images (e.g., Docker Hub). |
| **Volume** | Persistent storage mechanism for containers. |
| **Network** | Allows containers to communicate with each other. |

### The Image-Container Relationship

```
┌─────────────────────────────────────────────────────────────┐
│                         IMAGE                                │
│                    (Read-only layers)                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Layer 4: Application code (COPY . /app)                 ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Layer 3: Dependencies (RUN npm install)                 ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Layer 2: Node.js (FROM node:18)                         ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Layer 1: Base OS (Debian/Alpine)                        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                           │
                           │ docker run
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                       CONTAINER                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Writable layer (Container layer)                        ││ ← Changes here
│  ├─────────────────────────────────────────────────────────┤│
│  │ Layer 4: Application code                   (read-only) ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Layer 3: Dependencies                       (read-only) ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Layer 2: Node.js                            (read-only) ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Layer 1: Base OS                            (read-only) ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Installation & Setup

### macOS

```bash
# Option 1: Docker Desktop (Recommended for beginners)
# Download from: https://www.docker.com/products/docker-desktop

# Option 2: Using Homebrew
brew install --cask docker
```

### Linux (Ubuntu/Debian)

```bash
# Update package index
sudo apt-get update

# Install prerequisites
sudo apt-get install ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER
```

### Verify Installation

```bash
# Check Docker version
docker --version

# Run test container
docker run hello-world
```

---

## 4. Basic Commands

### Container Lifecycle

```
                    ┌─────────┐
                    │ Created │
                    └────┬────┘
                         │ docker start
                         ▼
┌──────────┐       ┌─────────┐       ┌─────────┐
│ Restarting│◄─────│ Running │──────►│ Paused  │
└──────────┘       └────┬────┘       └─────────┘
     ▲                  │ docker stop
     │                  ▼
     │             ┌─────────┐
     └─────────────│ Stopped │
                   └────┬────┘
                        │ docker rm
                        ▼
                   ┌─────────┐
                   │ Deleted │
                   └─────────┘
```

### Essential Commands Cheatsheet

```bash
# ─────────────────────────────────────────────────────────────
# CONTAINER COMMANDS
# ─────────────────────────────────────────────────────────────

# Run a container
docker run <image>                    # Run in foreground
docker run -d <image>                 # Run in background (detached)
docker run -it <image> /bin/bash      # Run interactively with terminal
docker run --name myapp <image>       # Run with custom name
docker run -p 8080:80 <image>         # Map port 8080 (host) to 80 (container)
docker run -e VAR=value <image>       # Set environment variable
docker run --rm <image>               # Auto-remove when stopped

# List containers
docker ps                             # Running containers
docker ps -a                          # All containers (including stopped)

# Container management
docker start <container>              # Start a stopped container
docker stop <container>               # Stop gracefully (SIGTERM)
docker kill <container>               # Force stop (SIGKILL)
docker restart <container>            # Restart container
docker rm <container>                 # Remove container
docker rm -f <container>              # Force remove (even if running)

# Interact with running containers
docker exec -it <container> /bin/bash # Open shell in container
docker exec <container> <command>     # Run command in container
docker logs <container>               # View logs
docker logs -f <container>            # Follow logs (like tail -f)

# Container info
docker inspect <container>            # Detailed container info (JSON)
docker stats                          # Live resource usage
docker top <container>                # Running processes in container

# ─────────────────────────────────────────────────────────────
# IMAGE COMMANDS
# ─────────────────────────────────────────────────────────────

# List images
docker images                         # List all local images
docker images -a                      # Include intermediate images

# Pull/Push images
docker pull <image>                   # Download image from registry
docker push <image>                   # Upload image to registry

# Build images
docker build -t myapp:1.0 .           # Build from Dockerfile in current dir
docker build -f Dockerfile.dev .      # Build from specific Dockerfile

# Remove images
docker rmi <image>                    # Remove image
docker image prune                    # Remove unused images
docker image prune -a                 # Remove all unused images

# ─────────────────────────────────────────────────────────────
# SYSTEM COMMANDS
# ─────────────────────────────────────────────────────────────

docker system df                      # Disk usage
docker system prune                   # Remove unused data
docker system prune -a --volumes      # Deep clean (CAREFUL!)
```

### Practical Examples

```bash
# Example 1: Run a web server
docker run -d -p 8080:80 --name my-nginx nginx
# Now visit http://localhost:8080

# Example 2: Run a database
docker run -d \
  --name my-postgres \
  -e POSTGRES_PASSWORD=secret \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  postgres:15

# Example 3: Run Python script
docker run -it --rm \
  -v $(pwd):/app \
  -w /app \
  python:3.11 \
  python script.py

# Example 4: Debug a container
docker run -it --rm ubuntu:22.04 /bin/bash
```

---

## 5. Working with Images

### Image Naming Convention

```
[registry/][username/]repository[:tag]

Examples:
  nginx                           → docker.io/library/nginx:latest
  nginx:1.25                      → docker.io/library/nginx:1.25
  myuser/myapp                    → docker.io/myuser/myapp:latest
  myuser/myapp:v1.0.0             → docker.io/myuser/myapp:v1.0.0
  gcr.io/project/image:tag        → Google Container Registry
  123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:latest → AWS ECR
```

### Pulling Images

```bash
# Pull latest
docker pull nginx

# Pull specific version
docker pull nginx:1.25-alpine

# Pull from specific registry
docker pull gcr.io/google-containers/nginx

# Pull all tags
docker pull -a nginx
```

### Image Layers Explained

```bash
# See layers of an image
docker history nginx

# Output:
# IMAGE          CREATED       CREATED BY                                      SIZE
# a8758716bb6a   2 weeks ago   CMD ["nginx" "-g" "daemon off;"]                0B
# <missing>      2 weeks ago   STOPSIGNAL SIGQUIT                              0B
# <missing>      2 weeks ago   EXPOSE 80                                       0B
# <missing>      2 weeks ago   ENTRYPOINT ["/docker-entrypoint.sh"]            0B
# <missing>      2 weeks ago   COPY 30-tune-worker-processes.sh /docker-ent…   4.62kB
# <missing>      2 weeks ago   COPY 20-envsubst-on-templates.sh /docker-ent…   3.02kB
# ... etc
```

### Saving and Loading Images

```bash
# Save image to tar file
docker save -o myapp.tar myapp:1.0

# Load image from tar file
docker load -i myapp.tar

# Export container filesystem
docker export <container> > container.tar

# Import as new image
docker import container.tar newimage:tag
```

---

## 6. Dockerfiles

### Anatomy of a Dockerfile

```dockerfile
# ─────────────────────────────────────────────────────────────
# BASE IMAGE
# ─────────────────────────────────────────────────────────────
FROM node:18-alpine

# ─────────────────────────────────────────────────────────────
# METADATA
# ─────────────────────────────────────────────────────────────
LABEL maintainer="your@email.com"
LABEL version="1.0"
LABEL description="My awesome application"

# ─────────────────────────────────────────────────────────────
# ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────────────────────
ENV NODE_ENV=production
ENV PORT=3000

# ─────────────────────────────────────────────────────────────
# ARGUMENTS (build-time variables)
# ─────────────────────────────────────────────────────────────
ARG BUILD_VERSION=1.0.0

# ─────────────────────────────────────────────────────────────
# WORKING DIRECTORY
# ─────────────────────────────────────────────────────────────
WORKDIR /app

# ─────────────────────────────────────────────────────────────
# COPY FILES
# ─────────────────────────────────────────────────────────────
# Copy package files first (for layer caching)
COPY package*.json ./

# ─────────────────────────────────────────────────────────────
# RUN COMMANDS
# ─────────────────────────────────────────────────────────────
RUN npm ci --only=production

# Copy rest of application
COPY . .

# ─────────────────────────────────────────────────────────────
# USER (security: don't run as root)
# ─────────────────────────────────────────────────────────────
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001
USER nextjs

# ─────────────────────────────────────────────────────────────
# EXPOSE PORT (documentation)
# ─────────────────────────────────────────────────────────────
EXPOSE 3000

# ─────────────────────────────────────────────────────────────
# HEALTHCHECK
# ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# ─────────────────────────────────────────────────────────────
# ENTRYPOINT vs CMD
# ─────────────────────────────────────────────────────────────
# ENTRYPOINT: The executable (rarely overridden)
# CMD: Default arguments (easily overridden)

ENTRYPOINT ["node"]
CMD ["server.js"]
```

### Dockerfile Instructions Reference

| Instruction | Purpose | Example |
|-------------|---------|---------|
| `FROM` | Base image | `FROM node:18-alpine` |
| `WORKDIR` | Set working directory | `WORKDIR /app` |
| `COPY` | Copy files from host | `COPY . .` |
| `ADD` | Copy + extract/download | `ADD app.tar.gz /app` |
| `RUN` | Execute command | `RUN npm install` |
| `ENV` | Set environment variable | `ENV NODE_ENV=production` |
| `ARG` | Build-time variable | `ARG VERSION=1.0` |
| `EXPOSE` | Document port | `EXPOSE 3000` |
| `USER` | Set user | `USER node` |
| `CMD` | Default command | `CMD ["npm", "start"]` |
| `ENTRYPOINT` | Container entrypoint | `ENTRYPOINT ["node"]` |
| `VOLUME` | Create mount point | `VOLUME /data` |
| `HEALTHCHECK` | Container health check | See above |

### ENTRYPOINT vs CMD

```dockerfile
# ─────────────────────────────────────────────────────────────
# SCENARIO 1: CMD only
# ─────────────────────────────────────────────────────────────
FROM ubuntu
CMD ["echo", "Hello World"]

# docker run myimage           → Hello World
# docker run myimage echo Hi   → Hi (CMD replaced)

# ─────────────────────────────────────────────────────────────
# SCENARIO 2: ENTRYPOINT only
# ─────────────────────────────────────────────────────────────
FROM ubuntu
ENTRYPOINT ["echo"]

# docker run myimage              → (empty line)
# docker run myimage Hello        → Hello
# docker run myimage Hello World  → Hello World

# ─────────────────────────────────────────────────────────────
# SCENARIO 3: ENTRYPOINT + CMD (Recommended pattern)
# ─────────────────────────────────────────────────────────────
FROM ubuntu
ENTRYPOINT ["echo"]
CMD ["Hello World"]

# docker run myimage         → Hello World (CMD as default args)
# docker run myimage Hi      → Hi (CMD replaced, ENTRYPOINT stays)
```

### Real-World Dockerfile Examples

#### Node.js Application

```dockerfile
FROM node:18-alpine

# Create app directory
WORKDIR /app

# Install dependencies first (layer caching)
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY . .

# Don't run as root
USER node

EXPOSE 3000

CMD ["node", "server.js"]
```

#### Python Application

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Go Application

```dockerfile
# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/main .

EXPOSE 8080

CMD ["./main"]
```

### .dockerignore

Create a `.dockerignore` file to exclude files from the build context:

```
# .dockerignore

# Dependencies
node_modules
__pycache__
venv
.venv

# Git
.git
.gitignore

# IDE
.idea
.vscode
*.swp

# Build outputs
dist
build
*.egg-info

# Tests
tests
test
coverage
.pytest_cache

# Documentation
docs
*.md
!README.md

# Environment files
.env
.env.local
*.env

# OS files
.DS_Store
Thumbs.db

# Docker
Dockerfile*
docker-compose*
.docker

# Logs
*.log
logs
```

---

## 7. Docker Volumes

### Why Volumes?

Containers are ephemeral - when they're removed, their data is lost. Volumes persist data beyond the container lifecycle.

### Types of Mounts

```
┌─────────────────────────────────────────────────────────────┐
│                     HOST MACHINE                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ /var/lib/docker/volumes/myvolume/_data                  ││ ← Named Volume
│  │ (Managed by Docker)                                     ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ /home/user/myproject                                    ││ ← Bind Mount
│  │ (Managed by you)                                        ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ tmpfs (in memory)                                       ││ ← tmpfs Mount
│  │ (Temporary, fast)                                       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      CONTAINER                               │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐      │
│  │ /app/data     │ │ /app/src      │ │ /app/cache    │      │
│  │ (volume)      │ │ (bind mount)  │ │ (tmpfs)       │      │
│  └───────────────┘ └───────────────┘ └───────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Volume Commands

```bash
# ─────────────────────────────────────────────────────────────
# NAMED VOLUMES
# ─────────────────────────────────────────────────────────────

# Create a volume
docker volume create mydata

# List volumes
docker volume ls

# Inspect volume
docker volume inspect mydata

# Remove volume
docker volume rm mydata

# Remove all unused volumes
docker volume prune

# Use volume with container
docker run -v mydata:/app/data myimage
# or (more explicit)
docker run --mount source=mydata,target=/app/data myimage

# ─────────────────────────────────────────────────────────────
# BIND MOUNTS
# ─────────────────────────────────────────────────────────────

# Mount current directory
docker run -v $(pwd):/app myimage

# Mount with read-only
docker run -v $(pwd):/app:ro myimage

# Using --mount syntax (more explicit)
docker run --mount type=bind,source=$(pwd),target=/app myimage

# ─────────────────────────────────────────────────────────────
# TMPFS MOUNTS
# ─────────────────────────────────────────────────────────────

# Create tmpfs mount
docker run --tmpfs /app/cache myimage

# With options
docker run --mount type=tmpfs,target=/app/cache,tmpfs-size=100m myimage
```

### Volume Use Cases

```bash
# Database persistence
docker run -d \
  --name postgres \
  -v pgdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=secret \
  postgres:15

# Development with hot reload
docker run -d \
  --name dev-server \
  -v $(pwd):/app \
  -v /app/node_modules \    # Anonymous volume to preserve node_modules
  -p 3000:3000 \
  node:18 npm run dev

# Share data between containers
docker volume create shared-data

docker run -d --name writer -v shared-data:/data alpine \
  sh -c "while true; do date >> /data/log.txt; sleep 1; done"

docker run --rm -v shared-data:/data alpine cat /data/log.txt
```

### Backup and Restore Volumes

```bash
# Backup a volume
docker run --rm \
  -v mydata:/source:ro \
  -v $(pwd):/backup \
  alpine tar czf /backup/mydata-backup.tar.gz -C /source .

# Restore a volume
docker run --rm \
  -v mydata:/target \
  -v $(pwd):/backup \
  alpine tar xzf /backup/mydata-backup.tar.gz -C /target
```

---

## 8. Docker Networking

### Network Types

```
┌─────────────────────────────────────────────────────────────┐
│                    BRIDGE (default)                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                  │
│  │Container│    │Container│    │Container│                  │
│  │   A     │    │   B     │    │   C     │                  │
│  └────┬────┘    └────┬────┘    └────┬────┘                  │
│       │              │              │                        │
│  ─────┴──────────────┴──────────────┴─────  docker0 bridge  │
│                      │                                       │
│                      │ NAT                                   │
│                      ▼                                       │
│                 Host Network                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       HOST                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Container shares host's network namespace               ││
│  │ No isolation - same IP as host                          ││
│  │ Best performance, least isolation                       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       NONE                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Container has no network access                         ││
│  │ Complete isolation                                      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      OVERLAY                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Multi-host networking                                   ││
│  │ Used with Docker Swarm / Kubernetes                     ││
│  │ Containers on different hosts can communicate           ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Network Commands

```bash
# List networks
docker network ls

# Create a network
docker network create mynetwork

# Create with specific driver
docker network create --driver bridge mynetwork

# Inspect network
docker network inspect mynetwork

# Connect container to network
docker network connect mynetwork mycontainer

# Disconnect container from network
docker network disconnect mynetwork mycontainer

# Remove network
docker network rm mynetwork

# Remove all unused networks
docker network prune
```

### Container Communication

```bash
# ─────────────────────────────────────────────────────────────
# DEFAULT BRIDGE NETWORK
# ─────────────────────────────────────────────────────────────
# Containers can communicate via IP addresses only

docker run -d --name web nginx
docker run -d --name app node
# app can reach web only via IP (docker inspect web to find IP)

# ─────────────────────────────────────────────────────────────
# USER-DEFINED BRIDGE NETWORK (Recommended)
# ─────────────────────────────────────────────────────────────
# Containers can communicate via container names (DNS)

docker network create myapp

docker run -d --name db --network myapp postgres:15
docker run -d --name api --network myapp myapi

# Inside 'api' container, can connect to 'db' by name:
# postgresql://db:5432/mydb

# ─────────────────────────────────────────────────────────────
# HOST NETWORK
# ─────────────────────────────────────────────────────────────
docker run -d --network host nginx
# Nginx is now available on host's port 80 directly

# ─────────────────────────────────────────────────────────────
# NO NETWORK
# ─────────────────────────────────────────────────────────────
docker run -d --network none alpine
```

### Port Mapping

```bash
# Map specific port
docker run -p 8080:80 nginx        # host:container

# Map to specific interface
docker run -p 127.0.0.1:8080:80 nginx

# Map range of ports
docker run -p 8080-8090:80-90 myapp

# Map random host port
docker run -p 80 nginx             # Random high port → 80
docker port <container>            # See the mapping

# Publish all exposed ports
docker run -P nginx                # All EXPOSE ports get random mapping
```

### Real-World Network Setup

```bash
# Create application network
docker network create webapp

# Start database
docker run -d \
  --name db \
  --network webapp \
  -v dbdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=myapp \
  postgres:15

# Start Redis
docker run -d \
  --name redis \
  --network webapp \
  redis:7-alpine

# Start API (can connect to 'db' and 'redis' by name)
docker run -d \
  --name api \
  --network webapp \
  -e DATABASE_URL=postgresql://postgres:secret@db:5432/myapp \
  -e REDIS_URL=redis://redis:6379 \
  -p 3000:3000 \
  myapi:latest

# Start frontend
docker run -d \
  --name frontend \
  --network webapp \
  -e API_URL=http://api:3000 \
  -p 80:80 \
  myfrontend:latest
```

---

## 9. Docker Compose

Docker Compose is a tool for defining and running multi-container applications.

### Basic Structure

```yaml
# docker-compose.yml

version: '3.8'  # Optional in newer versions

services:
  service_name:
    image: image_name
    # ... service configuration

volumes:
  volume_name:
    # ... volume configuration

networks:
  network_name:
    # ... network configuration
```

### Complete Example

```yaml
# docker-compose.yml
version: '3.8'

services:
  # ─────────────────────────────────────────────────────────
  # FRONTEND
  # ─────────────────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules  # Anonymous volume
    depends_on:
      - api
    networks:
      - webapp

  # ─────────────────────────────────────────────────────────
  # API
  # ─────────────────────────────────────────────────────────
  api:
    build:
      context: ./api
      args:
        - BUILD_ENV=development
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:secret@db:5432/myapp
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}  # From .env file
    volumes:
      - ./api:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - webapp
    restart: unless-stopped

  # ─────────────────────────────────────────────────────────
  # DATABASE
  # ─────────────────────────────────────────────────────────
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=myapp
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - webapp
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─────────────────────────────────────────────────────────
  # REDIS
  # ─────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    networks:
      - webapp
    command: redis-server --appendonly yes

  # ─────────────────────────────────────────────────────────
  # NGINX (Reverse Proxy)
  # ─────────────────────────────────────────────────────────
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - frontend
      - api
    networks:
      - webapp

# ─────────────────────────────────────────────────────────────
# VOLUMES
# ─────────────────────────────────────────────────────────────
volumes:
  pgdata:
  redisdata:

# ─────────────────────────────────────────────────────────────
# NETWORKS
# ─────────────────────────────────────────────────────────────
networks:
  webapp:
    driver: bridge
```

### Docker Compose Commands

```bash
# ─────────────────────────────────────────────────────────────
# LIFECYCLE
# ─────────────────────────────────────────────────────────────

# Start services
docker compose up                  # Foreground
docker compose up -d               # Detached (background)

# Start specific services
docker compose up api db

# Stop services
docker compose stop                # Stop without removing
docker compose down                # Stop and remove containers
docker compose down -v             # Also remove volumes
docker compose down --rmi all      # Also remove images

# Restart services
docker compose restart
docker compose restart api

# ─────────────────────────────────────────────────────────────
# BUILD
# ─────────────────────────────────────────────────────────────

# Build images
docker compose build

# Build and start
docker compose up --build

# Build without cache
docker compose build --no-cache

# ─────────────────────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────────────────────

# List containers
docker compose ps

# View logs
docker compose logs              # All services
docker compose logs api          # Specific service
docker compose logs -f           # Follow
docker compose logs --tail=100   # Last 100 lines

# ─────────────────────────────────────────────────────────────
# EXECUTION
# ─────────────────────────────────────────────────────────────

# Run command in service
docker compose exec api bash
docker compose exec db psql -U postgres

# Run one-off command
docker compose run --rm api npm test

# ─────────────────────────────────────────────────────────────
# SCALING
# ─────────────────────────────────────────────────────────────

# Scale service
docker compose up -d --scale api=3
```

### Development vs Production

```yaml
# docker-compose.yml (base)
version: '3.8'
services:
  api:
    build: ./api
    environment:
      - DATABASE_URL=postgresql://postgres:secret@db:5432/myapp

# docker-compose.override.yml (development - auto-loaded)
version: '3.8'
services:
  api:
    volumes:
      - ./api:/app
    environment:
      - DEBUG=true
    ports:
      - "8000:8000"

# docker-compose.prod.yml (production)
version: '3.8'
services:
  api:
    image: myregistry/api:${TAG}
    environment:
      - DEBUG=false
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

```bash
# Development (uses docker-compose.yml + docker-compose.override.yml)
docker compose up

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables

```yaml
# Option 1: Direct values
services:
  api:
    environment:
      - NODE_ENV=production
      - PORT=3000

# Option 2: From .env file (auto-loaded)
services:
  api:
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}

# Option 3: env_file
services:
  api:
    env_file:
      - .env
      - .env.local
```

---

## 10. Multi-Stage Builds

Multi-stage builds allow you to create smaller, more secure images by separating build and runtime environments.

### Why Multi-Stage?

```
SINGLE STAGE:
┌──────────────────────────────────────┐
│ Final Image: 1.2 GB                  │
│ ├── Build tools (gcc, make, etc.)   │
│ ├── Source code                      │
│ ├── Dev dependencies                 │
│ └── Application binary               │
└──────────────────────────────────────┘

MULTI-STAGE:
┌──────────────────────────────────────┐
│ Build Stage (discarded)              │
│ ├── Build tools                      │
│ ├── Source code                      │
│ └── Dev dependencies                 │
└───────────────┬──────────────────────┘
                │ COPY --from=builder
                ▼
┌──────────────────────────────────────┐
│ Final Image: 50 MB                   │
│ └── Application binary only          │
└──────────────────────────────────────┘
```

### Basic Pattern

```dockerfile
# ─────────────────────────────────────────────────────────────
# STAGE 1: Build
# ─────────────────────────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ─────────────────────────────────────────────────────────────
# STAGE 2: Production
# ─────────────────────────────────────────────────────────────
FROM node:18-alpine

WORKDIR /app

# Copy only production dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy built assets from builder stage
COPY --from=builder /app/dist ./dist

USER node

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

### Advanced Examples

#### React Application

```dockerfile
# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### Go Application

```dockerfile
# Build stage
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o main .

# Final stage - scratch (empty) image
FROM scratch
COPY --from=builder /app/main /main
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 8080
ENTRYPOINT ["/main"]
```

#### Python with Test Stage

```dockerfile
# Base stage
FROM python:3.11-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Test stage
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
RUN pytest tests/

# Production stage
FROM base AS production
COPY --from=test /app/src ./src
USER nobody
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0"]
```

### Building Specific Stages

```bash
# Build only up to a specific stage
docker build --target builder -t myapp:builder .

# Build the final stage (default)
docker build -t myapp:latest .

# Build test stage (runs tests during build)
docker build --target test -t myapp:test .
```

---

## 11. Best Practices

### Image Optimization

```dockerfile
# ─────────────────────────────────────────────────────────────
# 1. USE SMALL BASE IMAGES
# ─────────────────────────────────────────────────────────────
# Bad
FROM ubuntu:22.04        # ~77MB

# Better
FROM debian:slim         # ~27MB

# Best (when compatible)
FROM alpine:3.18         # ~7MB

# ─────────────────────────────────────────────────────────────
# 2. MINIMIZE LAYERS
# ─────────────────────────────────────────────────────────────
# Bad - Each RUN creates a layer
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y git
RUN rm -rf /var/lib/apt/lists/*

# Good - Single layer, cleanup in same layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git && \
    rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────
# 3. ORDER LAYERS BY CHANGE FREQUENCY
# ─────────────────────────────────────────────────────────────
# Put rarely-changing layers first for better caching

FROM node:18-alpine

# Rarely changes - cached
WORKDIR /app

# Changes occasionally - cached most of the time
COPY package*.json ./
RUN npm ci --only=production

# Changes frequently - not cached, but layers above are
COPY . .

# ─────────────────────────────────────────────────────────────
# 4. USE SPECIFIC TAGS
# ─────────────────────────────────────────────────────────────
# Bad - unpredictable
FROM node:latest

# Good - predictable
FROM node:18.17.1-alpine3.18
```

### Security Best Practices

```dockerfile
# ─────────────────────────────────────────────────────────────
# 1. DON'T RUN AS ROOT
# ─────────────────────────────────────────────────────────────
FROM node:18-alpine

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

WORKDIR /app
COPY --chown=nextjs:nodejs . .

USER nextjs
CMD ["node", "server.js"]

# ─────────────────────────────────────────────────────────────
# 2. USE MULTI-STAGE BUILDS
# ─────────────────────────────────────────────────────────────
# Don't include build tools in production image

# ─────────────────────────────────────────────────────────────
# 3. SCAN FOR VULNERABILITIES
# ─────────────────────────────────────────────────────────────
# Use: docker scout cve <image>
# Or: trivy image <image>

# ─────────────────────────────────────────────────────────────
# 4. DON'T STORE SECRETS IN IMAGES
# ─────────────────────────────────────────────────────────────
# Bad
ENV API_KEY=secret123

# Good - pass at runtime
# docker run -e API_KEY=$API_KEY myimage

# ─────────────────────────────────────────────────────────────
# 5. USE .dockerignore
# ─────────────────────────────────────────────────────────────
# Exclude sensitive files from build context
```

### Resource Management

```yaml
# docker-compose.yml
services:
  api:
    image: myapi
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Logging Best Practices

```bash
# View logs
docker logs mycontainer

# Follow logs
docker logs -f mycontainer

# Timestamps
docker logs -t mycontainer

# Configure logging driver
docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  myimage
```

### Development Workflow

```yaml
# docker-compose.yml for development
version: '3.8'
services:
  app:
    build:
      context: .
      target: development
    volumes:
      - .:/app                    # Mount source code
      - /app/node_modules         # Preserve node_modules
    environment:
      - NODE_ENV=development
      - DEBUG=*
    command: npm run dev          # Hot reload
    ports:
      - "3000:3000"
      - "9229:9229"               # Debug port
```

---

## 12. Production Deployment

### Container Orchestration Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  ORCHESTRATION OPTIONS                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Docker Compose    →  Single host, simple deployments        │
│                                                              │
│  Docker Swarm      →  Multi-host, built into Docker          │
│                                                              │
│  Kubernetes (K8s)  →  Multi-host, industry standard,         │
│                       complex but powerful                   │
│                                                              │
│  AWS ECS/Fargate   →  AWS managed containers                 │
│                                                              │
│  Google Cloud Run  →  Serverless containers                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Production Dockerfile

```dockerfile
# Production-optimized Dockerfile
FROM node:18-alpine AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

# Build the application
FROM base AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production image
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

# Don't run as root
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder --chown=nextjs:nodejs /app/dist ./dist
COPY --from=deps --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./

USER nextjs

EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/server.js"]
```

### CI/CD Pipeline Example (GitHub Actions)

```yaml
# .github/workflows/docker.yml
name: Build and Push Docker Image

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=ref,event=branch
            type=semver,pattern={{version}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Cloud Deployment Examples

#### AWS ECS Task Definition

```json
{
  "family": "myapp",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:latest",
      "portMappings": [
        {
          "containerPort": 3000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "NODE_ENV",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:myapp/db-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/myapp",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:3000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512"
}
```

#### Google Cloud Run

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/myapp

# Deploy to Cloud Run
gcloud run deploy myapp \
  --image gcr.io/PROJECT_ID/myapp \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "NODE_ENV=production" \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 10
```

---

## 13. Debugging & Troubleshooting

### Common Issues and Solutions

```bash
# ─────────────────────────────────────────────────────────────
# CONTAINER WON'T START
# ─────────────────────────────────────────────────────────────

# Check logs
docker logs mycontainer

# Check exit code
docker inspect mycontainer --format='{{.State.ExitCode}}'

# Run interactively to see errors
docker run -it myimage /bin/sh

# ─────────────────────────────────────────────────────────────
# CONTAINER EXITS IMMEDIATELY
# ─────────────────────────────────────────────────────────────

# Usually means the main process exited
# Make sure CMD/ENTRYPOINT runs a foreground process

# Bad: process backgrounds itself
CMD ["nginx"]

# Good: run in foreground
CMD ["nginx", "-g", "daemon off;"]

# ─────────────────────────────────────────────────────────────
# CAN'T CONNECT TO CONTAINER
# ─────────────────────────────────────────────────────────────

# Check if container is running
docker ps

# Check port mapping
docker port mycontainer

# Check if service is listening inside container
docker exec mycontainer netstat -tlnp

# Check container IP
docker inspect mycontainer | grep IPAddress

# ─────────────────────────────────────────────────────────────
# OUT OF DISK SPACE
# ─────────────────────────────────────────────────────────────

# Check Docker disk usage
docker system df

# Clean up
docker system prune -a --volumes

# ─────────────────────────────────────────────────────────────
# SLOW BUILDS
# ─────────────────────────────────────────────────────────────

# Use BuildKit (faster, better caching)
DOCKER_BUILDKIT=1 docker build .

# Check what's being copied (.dockerignore missing?)
docker build --no-cache . 2>&1 | head -20
```

### Debugging Tools

```bash
# ─────────────────────────────────────────────────────────────
# INSPECT CONTAINER
# ─────────────────────────────────────────────────────────────

# Full inspection
docker inspect mycontainer

# Specific fields
docker inspect -f '{{.State.Status}}' mycontainer
docker inspect -f '{{.NetworkSettings.IPAddress}}' mycontainer
docker inspect -f '{{json .Config.Env}}' mycontainer | jq

# ─────────────────────────────────────────────────────────────
# EXEC INTO CONTAINER
# ─────────────────────────────────────────────────────────────

# Interactive shell
docker exec -it mycontainer /bin/bash
docker exec -it mycontainer /bin/sh  # Alpine

# Run as root (even if USER is set)
docker exec -u root -it mycontainer /bin/sh

# ─────────────────────────────────────────────────────────────
# VIEW PROCESSES
# ─────────────────────────────────────────────────────────────

docker top mycontainer

# ─────────────────────────────────────────────────────────────
# RESOURCE USAGE
# ─────────────────────────────────────────────────────────────

# Live stats
docker stats

# Specific container
docker stats mycontainer

# ─────────────────────────────────────────────────────────────
# COPY FILES
# ─────────────────────────────────────────────────────────────

# From container to host
docker cp mycontainer:/app/log.txt ./log.txt

# From host to container
docker cp ./config.json mycontainer:/app/config.json

# ─────────────────────────────────────────────────────────────
# DIFF (see what changed)
# ─────────────────────────────────────────────────────────────

docker diff mycontainer
# A = Added, C = Changed, D = Deleted
```

### Debugging Network Issues

```bash
# List networks
docker network ls

# Inspect network
docker network inspect mynetwork

# Check container's networks
docker inspect mycontainer -f '{{json .NetworkSettings.Networks}}' | jq

# Test connectivity between containers
docker exec container1 ping container2
docker exec container1 curl http://container2:3000

# DNS debugging
docker exec mycontainer nslookup other-container

# Check iptables rules (Linux)
sudo iptables -L -n -v | grep -i docker
```

---

## 14. Advanced Topics

### Docker BuildKit

BuildKit is Docker's next-generation build system with advanced features:

```dockerfile
# syntax=docker/dockerfile:1.4

# ─────────────────────────────────────────────────────────────
# CACHE MOUNTS (cache dependencies between builds)
# ─────────────────────────────────────────────────────────────
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .

# ─────────────────────────────────────────────────────────────
# SECRET MOUNTS (don't embed secrets in layers)
# ─────────────────────────────────────────────────────────────
FROM alpine
RUN --mount=type=secret,id=github_token \
    cat /run/secrets/github_token

# Build with:
# docker build --secret id=github_token,src=./token.txt .

# ─────────────────────────────────────────────────────────────
# SSH MOUNTS (for private repos)
# ─────────────────────────────────────────────────────────────
FROM alpine
RUN --mount=type=ssh \
    git clone git@github.com:private/repo.git

# Build with:
# docker build --ssh default .
```

```bash
# Enable BuildKit
export DOCKER_BUILDKIT=1

# Or in Docker Desktop, enable in settings

# Build with progress output
docker build --progress=plain .
```

### Docker Contexts

Manage multiple Docker environments:

```bash
# List contexts
docker context ls

# Create context for remote Docker
docker context create production \
  --docker "host=ssh://user@production-server"

# Use context
docker context use production

# Run command in specific context
docker --context production ps
```

### Container Security Scanning

```bash
# Docker Scout (built-in)
docker scout cve myimage
docker scout recommendations myimage

# Trivy (popular open source)
trivy image myimage

# Snyk
snyk container test myimage
```

### Docker in Docker (DinD)

```yaml
# CI/CD use case
services:
  docker:
    image: docker:dind
    privileged: true
    environment:
      - DOCKER_TLS_CERTDIR=/certs
    volumes:
      - docker-certs:/certs

  runner:
    image: docker:cli
    environment:
      - DOCKER_HOST=tcp://docker:2376
      - DOCKER_TLS_VERIFY=1
      - DOCKER_CERT_PATH=/certs/client
    volumes:
      - docker-certs:/certs:ro
    depends_on:
      - docker

volumes:
  docker-certs:
```

### Resource Constraints

```bash
# Memory limits
docker run -m 512m myimage                    # Hard limit
docker run --memory-reservation 256m myimage  # Soft limit

# CPU limits
docker run --cpus 0.5 myimage                 # 50% of one CPU
docker run --cpu-shares 512 myimage           # Relative weight

# Combined
docker run \
  --memory 512m \
  --memory-swap 1g \
  --cpus 0.5 \
  --pids-limit 100 \
  myimage
```

### Docker API

```bash
# Enable API (be careful with security!)
# In /etc/docker/daemon.json:
{
  "hosts": ["unix:///var/run/docker.sock", "tcp://0.0.0.0:2375"]
}

# Example API calls
curl --unix-socket /var/run/docker.sock http://localhost/containers/json
curl --unix-socket /var/run/docker.sock http://localhost/images/json
```

### Useful Aliases

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Docker aliases
alias d='docker'
alias dc='docker compose'
alias dps='docker ps'
alias dpsa='docker ps -a'
alias di='docker images'
alias drm='docker rm'
alias drmi='docker rmi'
alias dex='docker exec -it'
alias dlogs='docker logs -f'

# Clean up
alias dprune='docker system prune -af --volumes'

# Stop all containers
alias dstopall='docker stop $(docker ps -q)'

# Remove all containers
alias drmall='docker rm $(docker ps -aq)'

# Remove all images
alias drmiall='docker rmi $(docker images -q)'

# Docker compose shortcuts
alias dcup='docker compose up -d'
alias dcdown='docker compose down'
alias dclogs='docker compose logs -f'
alias dcbuild='docker compose build'
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                   DOCKER QUICK REFERENCE                     │
├─────────────────────────────────────────────────────────────┤
│ CONTAINERS                                                   │
│   docker run -d -p 8080:80 --name web nginx                 │
│   docker ps / docker ps -a                                  │
│   docker stop/start/restart <container>                     │
│   docker rm <container>                                     │
│   docker exec -it <container> /bin/sh                       │
│   docker logs -f <container>                                │
├─────────────────────────────────────────────────────────────┤
│ IMAGES                                                       │
│   docker build -t myapp:1.0 .                               │
│   docker images                                             │
│   docker pull/push <image>                                  │
│   docker rmi <image>                                        │
├─────────────────────────────────────────────────────────────┤
│ VOLUMES                                                      │
│   docker volume create/ls/rm/inspect                        │
│   docker run -v myvolume:/data                              │
│   docker run -v $(pwd):/app                                 │
├─────────────────────────────────────────────────────────────┤
│ NETWORKS                                                     │
│   docker network create/ls/rm/inspect                       │
│   docker run --network mynet                                │
│   docker network connect mynet <container>                  │
├─────────────────────────────────────────────────────────────┤
│ COMPOSE                                                      │
│   docker compose up -d                                      │
│   docker compose down                                       │
│   docker compose logs -f                                    │
│   docker compose exec <service> /bin/sh                     │
├─────────────────────────────────────────────────────────────┤
│ CLEANUP                                                      │
│   docker system prune -a --volumes                          │
│   docker container prune                                    │
│   docker image prune -a                                     │
│   docker volume prune                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Practice**: Build Dockerfiles for your existing projects
2. **Learn Kubernetes**: Natural next step after Docker
3. **Study Security**: Container security is crucial
4. **Explore CI/CD**: Automate your Docker workflows
5. **Certifications**: Consider Docker Certified Associate (DCA)

## Resources

- [Official Docker Documentation](https://docs.docker.com/)
- [Docker Hub](https://hub.docker.com/)
- [Play with Docker](https://labs.play-with-docker.com/) - Free online playground
- [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Docker Compose Specification](https://docs.docker.com/compose/compose-file/)

---

## 15. Practice Questions

Test your Docker knowledge with these questions organized by difficulty level.

---

### Level 1: Beginner (Fundamentals)

#### Conceptual Questions

**Q1.** What is the main difference between a container and a virtual machine?

<details>
<summary>Answer</summary>

Containers share the host OS kernel and isolate processes at the application level, making them lightweight (MBs) and fast to start (seconds). Virtual machines include a full guest OS with its own kernel, requiring a hypervisor, making them heavier (GBs) and slower to start (minutes). Containers provide process-level isolation while VMs provide hardware-level isolation.
</details>

---

**Q2.** What is the relationship between a Docker image and a container?

<details>
<summary>Answer</summary>

An image is a read-only template containing instructions for creating a container. A container is a runnable instance of an image. Think of it like a class (image) and object (container) in OOP. You can create multiple containers from the same image, and each container has its own writable layer on top of the read-only image layers.
</details>

---

**Q3.** What is Docker Hub?

<details>
<summary>Answer</summary>

Docker Hub is the default public registry for Docker images. It's a cloud-based repository where you can find, store, and distribute container images. It contains official images (like nginx, postgres, node) and user-created images. Other registries include Amazon ECR, Google Container Registry, and GitHub Container Registry.
</details>

---

**Q4.** What does the `-d` flag do in `docker run -d nginx`?

<details>
<summary>Answer</summary>

The `-d` flag runs the container in detached mode (in the background). Without it, the container runs in the foreground and your terminal is attached to the container's output. With `-d`, the command returns immediately with the container ID, and the container runs in the background.
</details>

---

**Q5.** What is the purpose of the `docker ps` command? How do you see stopped containers?

<details>
<summary>Answer</summary>

`docker ps` lists all currently running containers. To see all containers including stopped ones, use `docker ps -a`. The output shows container ID, image, command, creation time, status, ports, and names.
</details>

---

#### Practical Questions

**Q6.** Write the command to:
- Run an nginx container in the background
- Name it "webserver"
- Map port 8080 on your machine to port 80 in the container

<details>
<summary>Answer</summary>

```bash
docker run -d --name webserver -p 8080:80 nginx
```
</details>

---

**Q7.** How do you view the logs of a running container named "myapp"? How do you follow the logs in real-time?

<details>
<summary>Answer</summary>

```bash
# View logs
docker logs myapp

# Follow logs in real-time
docker logs -f myapp

# View last 100 lines and follow
docker logs --tail 100 -f myapp
```
</details>

---

**Q8.** Write the command to open an interactive bash shell inside a running container named "mycontainer".

<details>
<summary>Answer</summary>

```bash
docker exec -it mycontainer /bin/bash

# For Alpine-based images (no bash):
docker exec -it mycontainer /bin/sh
```
</details>

---

**Q9.** How do you stop and remove a container named "oldapp"?

<details>
<summary>Answer</summary>

```bash
# Stop then remove
docker stop oldapp
docker rm oldapp

# Or force remove (even if running)
docker rm -f oldapp
```
</details>

---

**Q10.** What command shows you all Docker images on your local machine?

<details>
<summary>Answer</summary>

```bash
docker images
# or
docker image ls
```
</details>

---

### Level 2: Elementary (Basic Operations)

#### Conceptual Questions

**Q11.** Explain the difference between `COPY` and `ADD` in a Dockerfile.

<details>
<summary>Answer</summary>

Both copy files from the host to the image, but:
- `COPY` simply copies files/directories from source to destination
- `ADD` has extra features: it can extract tar archives automatically and download files from URLs

Best practice: Use `COPY` unless you specifically need `ADD`'s extra features, as `COPY` is more transparent and predictable.

```dockerfile
COPY ./app /app           # Simple copy
ADD app.tar.gz /app       # Extracts automatically
ADD https://example.com/file /app/  # Downloads (not recommended)
```
</details>

---

**Q12.** What is a Docker layer? Why does layer order matter in a Dockerfile?

<details>
<summary>Answer</summary>

Each instruction in a Dockerfile creates a layer. Layers are cached and reused to speed up builds. If a layer changes, all subsequent layers must be rebuilt.

Order matters for caching efficiency:
```dockerfile
# Good: Dependencies change less often than code
COPY package.json ./
RUN npm install
COPY . .              # Code changes only rebuild from here

# Bad: Any code change rebuilds everything
COPY . .
RUN npm install
```
</details>

---

**Q13.** What is the purpose of `.dockerignore`?

<details>
<summary>Answer</summary>

`.dockerignore` excludes files and directories from the build context sent to the Docker daemon. Benefits:
- Smaller build context = faster builds
- Prevents sensitive files from being included (`.env`, credentials)
- Excludes unnecessary files (`node_modules`, `.git`, logs)

```
# .dockerignore
node_modules
.git
.env
*.log
```
</details>

---

**Q14.** What's the difference between `docker stop` and `docker kill`?

<details>
<summary>Answer</summary>

- `docker stop` sends SIGTERM, waits for graceful shutdown (default 10 seconds), then sends SIGKILL
- `docker kill` immediately sends SIGKILL, forcing immediate termination

Use `stop` for graceful shutdown (allows cleanup), `kill` when container is unresponsive.
</details>

---

**Q15.** What does `EXPOSE 3000` do in a Dockerfile?

<details>
<summary>Answer</summary>

`EXPOSE` is documentation that indicates which ports the container listens on. It does NOT actually publish the port. To publish ports, you must use `-p` flag at runtime:

```dockerfile
EXPOSE 3000  # Documentation only
```

```bash
docker run -p 3000:3000 myimage  # Actually publishes the port
```
</details>

---

#### Practical Questions

**Q16.** Write a simple Dockerfile for a Node.js application that:
- Uses Node 18 Alpine as base
- Sets working directory to /app
- Copies package.json and installs dependencies
- Copies the rest of the code
- Exposes port 3000
- Runs `node server.js`

<details>
<summary>Answer</summary>

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["node", "server.js"]
```
</details>

---

**Q17.** How do you build an image from a Dockerfile and tag it as "myapp:v1.0"?

<details>
<summary>Answer</summary>

```bash
# Build from current directory
docker build -t myapp:v1.0 .

# Build from specific Dockerfile
docker build -t myapp:v1.0 -f Dockerfile.prod .

# Build with build arguments
docker build -t myapp:v1.0 --build-arg VERSION=1.0 .
```
</details>

---

**Q18.** Write a command to run a PostgreSQL container with:
- Name: mydb
- Password: secret123
- Database name: testdb
- Port 5432 mapped
- A named volume "pgdata" for persistence

<details>
<summary>Answer</summary>

```bash
docker run -d \
  --name mydb \
  -e POSTGRES_PASSWORD=secret123 \
  -e POSTGRES_DB=testdb \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  postgres:15
```
</details>

---

**Q19.** How do you remove all stopped containers and unused images in one command?

<details>
<summary>Answer</summary>

```bash
# Remove unused data (stopped containers, unused networks, dangling images)
docker system prune

# Also remove unused images (not just dangling)
docker system prune -a

# Include volumes (careful!)
docker system prune -a --volumes
```
</details>

---

**Q20.** Write a command to copy a file from inside a container to your host machine.

<details>
<summary>Answer</summary>

```bash
# From container to host
docker cp mycontainer:/app/config.json ./config.json

# From host to container
docker cp ./newconfig.json mycontainer:/app/config.json
```
</details>

---

### Level 3: Intermediate (Volumes, Networks, Compose)

#### Conceptual Questions

**Q21.** Explain the three types of Docker mounts and when to use each.

<details>
<summary>Answer</summary>

1. **Named Volumes** (`-v myvolume:/data`)
   - Managed by Docker
   - Best for: Database storage, persistent application data
   - Survives container removal

2. **Bind Mounts** (`-v /host/path:/container/path`)
   - Maps host directory to container
   - Best for: Development (live code reload), sharing config files
   - Host has direct access to files

3. **tmpfs Mounts** (`--tmpfs /cache`)
   - Stored in host memory only
   - Best for: Sensitive data, temporary caches
   - Data lost when container stops
</details>

---

**Q22.** What is the difference between the default bridge network and a user-defined bridge network?

<details>
<summary>Answer</summary>

| Default Bridge | User-Defined Bridge |
|----------------|---------------------|
| Containers communicate via IP only | Containers communicate via container names (DNS) |
| All containers on same network | Better isolation between apps |
| No automatic DNS | Automatic DNS resolution |
| Legacy feature | Recommended approach |

```bash
# User-defined network
docker network create mynet
docker run --network mynet --name api myapi
docker run --network mynet --name db postgres
# 'api' can connect to 'db' using hostname 'db'
```
</details>

---

**Q23.** In Docker Compose, what does `depends_on` do? Does it wait for the dependency to be "ready"?

<details>
<summary>Answer</summary>

`depends_on` controls startup order - it ensures specified services start before the dependent service. However, it does NOT wait for the service to be "ready" (e.g., database accepting connections).

```yaml
services:
  api:
    depends_on:
      - db  # db container starts first, but may not be ready
  db:
    image: postgres
```

For true readiness, use `depends_on` with `condition`:
```yaml
services:
  api:
    depends_on:
      db:
        condition: service_healthy
  db:
    image: postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 5s
      timeout: 5s
      retries: 5
```
</details>

---

**Q24.** What is the difference between `CMD` and `ENTRYPOINT`?

<details>
<summary>Answer</summary>

- `CMD`: Provides default arguments that can be easily overridden at runtime
- `ENTRYPOINT`: Defines the executable that always runs (harder to override)

```dockerfile
# CMD only - easily overridden
CMD ["npm", "start"]
# docker run myimage npm test  → runs "npm test"

# ENTRYPOINT only - always runs
ENTRYPOINT ["npm"]
# docker run myimage start     → runs "npm start"
# docker run myimage test      → runs "npm test"

# Combined (recommended pattern)
ENTRYPOINT ["npm"]
CMD ["start"]
# docker run myimage          → runs "npm start"
# docker run myimage test     → runs "npm test"
```
</details>

---

**Q25.** How do environment variables work in Docker Compose? List three ways to set them.

<details>
<summary>Answer</summary>

```yaml
services:
  app:
    # Method 1: Direct values
    environment:
      - NODE_ENV=production
      - PORT=3000

    # Method 2: From .env file (variable substitution)
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DB_URL=${DATABASE_URL}

    # Method 3: env_file
    env_file:
      - .env
      - .env.local
```

Priority order (highest to lowest):
1. Compose file `environment` values
2. Shell environment variables
3. `.env` file
4. `env_file` contents
</details>

---

#### Practical Questions

**Q26.** Write a docker-compose.yml that sets up:
- A Node.js API service (build from ./api directory, port 3000)
- A PostgreSQL database (with volume for persistence)
- A custom network so they can communicate

<details>
<summary>Answer</summary>

```yaml
version: '3.8'

services:
  api:
    build: ./api
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://postgres:secret@db:5432/myapp
    depends_on:
      - db
    networks:
      - backend

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=myapp
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend

volumes:
  pgdata:

networks:
  backend:
```
</details>

---

**Q27.** How do you scale a service to 3 instances in Docker Compose? What consideration must you make for ports?

<details>
<summary>Answer</summary>

```bash
docker compose up -d --scale api=3
```

Port consideration: You cannot map the same host port to multiple containers. Either:

1. Don't map ports, access via internal network:
```yaml
services:
  api:
    # No ports mapping
```

2. Use port range:
```yaml
services:
  api:
    ports:
      - "3000-3002:3000"
```

3. Use a load balancer (nginx) in front.
</details>

---

**Q28.** Write a command to create a custom bridge network named "myapp-network" and run two containers (api and db) connected to it.

<details>
<summary>Answer</summary>

```bash
# Create network
docker network create myapp-network

# Run containers on the network
docker run -d --name db --network myapp-network postgres:15

docker run -d --name api --network myapp-network \
  -e DATABASE_HOST=db \
  -p 3000:3000 \
  myapi:latest

# Verify they can communicate
docker exec api ping db
```
</details>

---

**Q29.** You have a development setup where you want your local code changes to reflect immediately in the container. Write the docker-compose configuration for this.

<details>
<summary>Answer</summary>

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - .:/app                    # Mount current directory
      - /app/node_modules         # Anonymous volume to preserve node_modules
    environment:
      - NODE_ENV=development
    command: npm run dev          # Use hot-reload command
```

For the anonymous volume trick: this prevents the host's (possibly empty) node_modules from overwriting the container's installed dependencies.
</details>

---

**Q30.** How do you backup a Docker named volume to a tar file?

<details>
<summary>Answer</summary>

```bash
# Backup
docker run --rm \
  -v myvolume:/source:ro \
  -v $(pwd):/backup \
  alpine tar czf /backup/myvolume-backup.tar.gz -C /source .

# Restore
docker run --rm \
  -v myvolume:/target \
  -v $(pwd):/backup \
  alpine tar xzf /backup/myvolume-backup.tar.gz -C /target
```
</details>

---

### Level 4: Advanced (Multi-stage, Security, Production)

#### Conceptual Questions

**Q31.** What is a multi-stage build and why would you use it?

<details>
<summary>Answer</summary>

Multi-stage builds use multiple `FROM` statements to create intermediate images, copying only needed artifacts to the final image.

Benefits:
- Smaller final images (no build tools, source code)
- Better security (fewer attack surfaces)
- Cleaner Dockerfiles

```dockerfile
# Build stage
FROM node:18 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage - only copy built assets
FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
CMD ["node", "dist/server.js"]
```

Result: Build tools, source code, and dev dependencies are NOT in the final image.
</details>

---

**Q32.** Explain why you should NOT run containers as root. How do you create and use a non-root user?

<details>
<summary>Answer</summary>

Running as root is dangerous because:
- If container is compromised, attacker has root access
- Root in container may have elevated privileges on host
- Violates principle of least privilege

Creating non-root user:
```dockerfile
FROM node:18-alpine

# Create user and group
RUN addgroup -g 1001 -S nodejs && \
    adduser -S -u 1001 -G nodejs appuser

WORKDIR /app
COPY --chown=appuser:nodejs . .

# Switch to non-root user
USER appuser

CMD ["node", "server.js"]
```
</details>

---

**Q33.** What is Docker layer caching? How can you optimize your Dockerfile to take advantage of it?

<details>
<summary>Answer</summary>

Docker caches each layer and reuses it if the instruction and context haven't changed. When a layer changes, all subsequent layers are rebuilt.

Optimization strategies:

1. **Order by change frequency** (least changing first):
```dockerfile
# Good
COPY package.json ./      # Changes rarely
RUN npm install           # Cached if package.json unchanged
COPY . .                  # Changes often, but above layers cached
```

2. **Combine RUN commands** to reduce layers:
```dockerfile
RUN apt-get update && \
    apt-get install -y curl git && \
    rm -rf /var/lib/apt/lists/*
```

3. **Use .dockerignore** to prevent unnecessary cache invalidation

4. **Use BuildKit cache mounts** for package managers:
```dockerfile
RUN --mount=type=cache,target=/root/.npm npm ci
```
</details>

---

**Q34.** What is a healthcheck in Docker? Write a healthcheck for a web application.

<details>
<summary>Answer</summary>

Healthcheck lets Docker monitor container health and restart unhealthy containers (in Swarm/orchestrators).

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1
```

Parameters:
- `--interval`: Time between checks (default 30s)
- `--timeout`: Max time for check to complete (default 30s)
- `--start-period`: Grace period on startup (default 0s)
- `--retries`: Failures before "unhealthy" (default 3)

In docker-compose:
```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```
</details>

---

**Q35.** Explain ARG vs ENV in Dockerfile. When would you use each?

<details>
<summary>Answer</summary>

| ARG | ENV |
|-----|-----|
| Available only during build | Available during build AND runtime |
| Not persisted in final image | Persisted in final image |
| Set with `--build-arg` | Set with `-e` at runtime |

```dockerfile
# ARG: build-time only
ARG NODE_VERSION=18
FROM node:${NODE_VERSION}

# ARG with default, overridable at build
ARG BUILD_ENV=production
RUN echo "Building for $BUILD_ENV"

# ENV: persisted at runtime
ENV NODE_ENV=production
ENV PORT=3000

# Convert ARG to ENV if needed at runtime
ARG API_VERSION
ENV API_VERSION=${API_VERSION}
```

```bash
# Override at build time
docker build --build-arg BUILD_ENV=development .

# Override ENV at runtime
docker run -e PORT=8080 myimage
```
</details>

---

#### Practical Questions

**Q36.** Write a multi-stage Dockerfile for a Go application that results in the smallest possible image.

<details>
<summary>Answer</summary>

```dockerfile
# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Build static binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-w -s" -o main .

# Final stage - scratch (empty) image
FROM scratch

# Copy CA certificates for HTTPS
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Copy binary
COPY --from=builder /app/main /main

EXPOSE 8080

ENTRYPOINT ["/main"]
```

This produces an image of just a few MBs (only the binary + CA certs).
</details>

---

**Q37.** Write a production docker-compose.yml with:
- Resource limits (CPU and memory)
- Healthchecks
- Restart policies
- Logging configuration

<details>
<summary>Answer</summary>

```yaml
version: '3.8'

services:
  api:
    image: myapi:latest
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production

  db:
    image: postgres:15-alpine
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```
</details>

---

**Q38.** A container keeps crashing. Write the commands you would use to debug it.

<details>
<summary>Answer</summary>

```bash
# 1. Check container status and exit code
docker ps -a
docker inspect mycontainer --format='{{.State.ExitCode}}'
docker inspect mycontainer --format='{{.State.Error}}'

# 2. View logs
docker logs mycontainer
docker logs --tail 100 mycontainer

# 3. Check what the container was running
docker inspect mycontainer --format='{{.Config.Cmd}}'
docker inspect mycontainer --format='{{.Config.Entrypoint}}'

# 4. Run container interactively to see errors
docker run -it myimage /bin/sh

# 5. Override entrypoint to get shell access
docker run -it --entrypoint /bin/sh myimage

# 6. Check resource usage (if it's OOM)
docker stats mycontainer

# 7. Check events
docker events --filter container=mycontainer

# 8. If container runs briefly, capture output
docker run --rm myimage 2>&1 | head -50
```
</details>

---

**Q39.** How do you pass secrets to a Docker container securely? Show multiple approaches.

<details>
<summary>Answer</summary>

```bash
# ❌ BAD: Hardcoded in Dockerfile
ENV API_KEY=secret123  # Visible in image layers!

# ✅ Method 1: Runtime environment variables
docker run -e API_KEY="$API_KEY" myimage

# ✅ Method 2: Environment file (not committed to git)
docker run --env-file .env myimage

# ✅ Method 3: Docker secrets (Swarm mode)
echo "secret123" | docker secret create api_key -
docker service create --secret api_key myimage
# Secret available at /run/secrets/api_key

# ✅ Method 4: BuildKit secrets (build time only)
docker build --secret id=mysecret,src=./secret.txt .
# In Dockerfile:
RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret

# ✅ Method 5: External secret manager
# AWS Secrets Manager, HashiCorp Vault, etc.
# Application fetches secrets at runtime
```
</details>

---

**Q40.** Write a Dockerfile that includes a test stage. The build should fail if tests don't pass.

<details>
<summary>Answer</summary>

```dockerfile
# Base stage
FROM node:18-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Test stage
FROM base AS test
COPY . .
# This layer fails if tests fail, stopping the build
RUN npm run test

# Build stage (only reached if tests pass)
FROM base AS builder
COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine AS production
WORKDIR /app

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

COPY --from=builder --chown=nextjs:nodejs /app/dist ./dist
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules

USER nextjs
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

```bash
# Build runs tests automatically
docker build -t myapp .

# Build only test stage
docker build --target test -t myapp:test .
```
</details>

---

### Level 5: Expert (Architecture, Orchestration, CI/CD)

#### Conceptual Questions

**Q41.** Explain Docker's copy-on-write (CoW) strategy and its implications for container performance.

<details>
<summary>Answer</summary>

Copy-on-write means containers share image layers (read-only) and only copy files to the writable layer when modified.

```
Image Layers (shared, read-only):
├── Layer 3: App code
├── Layer 2: Dependencies
├── Layer 1: Base OS
            ↓
Container A         Container B
├── Writable Layer  ├── Writable Layer
│   (changes only)  │   (changes only)
```

Implications:
- **Fast startup**: No need to copy entire filesystem
- **Memory efficient**: Shared layers across containers
- **Storage efficient**: Base layers stored once

Performance considerations:
- Heavy write workloads suffer (copy overhead)
- Use volumes for write-intensive data (databases)
- Storage driver matters (overlay2 recommended)
</details>

---

**Q42.** What is the difference between Docker Swarm and Kubernetes? When would you choose each?

<details>
<summary>Answer</summary>

| Aspect | Docker Swarm | Kubernetes |
|--------|--------------|------------|
| Complexity | Simple, built into Docker | Complex, steep learning curve |
| Setup | Minutes | Hours/Days |
| Scaling | Good | Excellent |
| Features | Basic orchestration | Full-featured platform |
| Community | Smaller | Massive ecosystem |
| Auto-healing | Basic | Advanced |
| Load balancing | Built-in | Flexible options |

**Choose Swarm when:**
- Small to medium deployments
- Team is Docker-focused
- Need quick setup
- Simpler requirements

**Choose Kubernetes when:**
- Large scale deployments
- Need advanced features (auto-scaling, service mesh)
- Multi-cloud strategy
- Complex microservices architecture
- Industry standard requirement
</details>

---

**Q43.** Explain the Docker build context. What happens when you run `docker build .`?

<details>
<summary>Answer</summary>

Build context is the set of files sent to the Docker daemon for building. When you run `docker build .`:

1. Docker client tars the current directory (build context)
2. Sends tar to Docker daemon
3. Daemon extracts and uses files for COPY/ADD instructions

```
Your Directory          Build Context (sent to daemon)
├── src/               ├── src/
├── node_modules/  ──► ├── node_modules/  (if no .dockerignore!)
├── .git/              ├── .git/
├── .env               ├── .env
└── Dockerfile         └── Dockerfile
```

Problems:
- Large contexts = slow builds
- Sensitive files may be included

Solutions:
```bash
# Check context size
docker build . 2>&1 | grep "Sending build context"

# Use .dockerignore
node_modules
.git
.env
*.log
```
</details>

---

**Q44.** How does Docker networking work under the hood? Explain bridge networking.

<details>
<summary>Answer</summary>

Docker creates a virtual bridge (`docker0`) on the host:

```
┌─────────────────────────────────────────────────────────┐
│ HOST                                                    │
│                                                         │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐        │
│  │Container1│     │Container2│     │Container3│        │
│  │172.17.0.2│     │172.17.0.3│     │172.17.0.4│        │
│  └────┬─────┘     └────┬─────┘     └────┬─────┘        │
│       │ veth           │ veth           │ veth          │
│       └────────────────┼────────────────┘               │
│                        │                                │
│              ┌─────────┴─────────┐                      │
│              │   docker0 bridge  │                      │
│              │    172.17.0.1     │                      │
│              └─────────┬─────────┘                      │
│                        │ NAT                            │
│              ┌─────────┴─────────┐                      │
│              │   eth0 (host)     │                      │
│              │   192.168.1.100   │                      │
│              └───────────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

Components:
- **veth pairs**: Virtual ethernet connecting container to bridge
- **docker0**: Virtual bridge (switch)
- **iptables**: NAT rules for external communication
- **DNS**: Docker's embedded DNS (127.0.0.11) for container name resolution

User-defined networks create separate bridges with automatic DNS resolution between containers.
</details>

---

**Q45.** What are Docker's storage drivers? When would you use different ones?

<details>
<summary>Answer</summary>

Storage drivers handle image and container layer storage:

| Driver | Best For | Notes |
|--------|----------|-------|
| **overlay2** | Most Linux (recommended) | Fast, efficient, default |
| **btrfs** | Btrfs filesystems | Requires btrfs |
| **zfs** | ZFS filesystems | Advanced features |
| **devicemapper** | Older RHEL/CentOS | Deprecated |
| **vfs** | Testing only | No CoW, slow |

Check current driver:
```bash
docker info | grep "Storage Driver"
```

Configure in `/etc/docker/daemon.json`:
```json
{
  "storage-driver": "overlay2"
}
```

Performance tip: For write-heavy workloads (databases), use volumes instead of relying on storage driver.
</details>

---

#### Practical Questions

**Q46.** Design a CI/CD pipeline (using GitHub Actions) that:
- Builds Docker image
- Runs tests
- Pushes to registry on main branch
- Uses caching for faster builds

<details>
<summary>Answer</summary>

```yaml
# .github/workflows/docker.yml
name: Docker CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=ref,event=branch
            type=semver,pattern={{version}}

      - name: Build test image
        uses: docker/build-push-action@v5
        with:
          context: .
          target: test
          load: true
          tags: ${{ env.IMAGE_NAME }}:test
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Run tests
        run: |
          docker run --rm ${{ env.IMAGE_NAME }}:test npm run test:ci

      - name: Build and push production
        if: github.event_name != 'pull_request'
        uses: docker/build-push-action@v5
        with:
          context: .
          target: production
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```
</details>

---

**Q47.** Write a docker-compose.yml for a microservices architecture with:
- API Gateway (nginx)
- Auth service
- User service
- Shared PostgreSQL database
- Redis for caching
- Proper network isolation (frontend/backend networks)

<details>
<summary>Answer</summary>

```yaml
version: '3.8'

services:
  # API Gateway - accessible externally
  gateway:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - auth-service
      - user-service
    networks:
      - frontend
    restart: unless-stopped

  # Auth Service
  auth-service:
    build: ./services/auth
    environment:
      - DATABASE_URL=postgresql://postgres:secret@db:5432/auth
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - frontend  # Reachable by gateway
      - backend   # Can reach db and redis
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  # User Service
  user-service:
    build: ./services/user
    environment:
      - DATABASE_URL=postgresql://postgres:secret@db:5432/users
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - frontend
      - backend
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  # PostgreSQL - only on backend network
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_PASSWORD=secret
      - POSTGRES_MULTIPLE_DATABASES=auth,users
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
    networks:
      - backend  # Not accessible from outside
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis - only on backend network
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redisdata:/data
    networks:
      - backend
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access
```
</details>

---

**Q48.** You need to debug a network issue between containers. Write the commands to diagnose the problem.

<details>
<summary>Answer</summary>

```bash
# 1. List all networks and find which network containers are on
docker network ls
docker inspect container1 --format='{{json .NetworkSettings.Networks}}' | jq
docker inspect container2 --format='{{json .NetworkSettings.Networks}}' | jq

# 2. Verify containers are on the same network
docker network inspect mynetwork

# 3. Check container IP addresses
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' container1
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' container2

# 4. Test connectivity from inside container
docker exec container1 ping container2
docker exec container1 ping 172.18.0.3  # by IP

# 5. Check DNS resolution
docker exec container1 nslookup container2
docker exec container1 cat /etc/resolv.conf

# 6. Check if port is listening in target container
docker exec container2 netstat -tlnp
docker exec container2 ss -tlnp

# 7. Test specific port connectivity
docker exec container1 nc -zv container2 3000
docker exec container1 curl -v http://container2:3000

# 8. Check for firewall/iptables issues (on host)
sudo iptables -L -n | grep -i docker
sudo iptables -L DOCKER -n -v

# 9. Check Docker daemon logs
sudo journalctl -u docker.service | tail -50

# 10. Use network debugging container
docker run --rm --net mynetwork nicolaka/netshoot \
  curl -v http://container2:3000
```
</details>

---

**Q49.** Implement a blue-green deployment strategy using Docker Compose.

<details>
<summary>Answer</summary>

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Nginx load balancer
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - app-blue
      - app-green
    networks:
      - frontend

  # Blue environment (current production)
  app-blue:
    image: myapp:${BLUE_VERSION:-latest}
    environment:
      - ENV_COLOR=blue
    networks:
      - frontend
    deploy:
      replicas: 2

  # Green environment (new version)
  app-green:
    image: myapp:${GREEN_VERSION:-latest}
    environment:
      - ENV_COLOR=green
    networks:
      - frontend
    deploy:
      replicas: 2

networks:
  frontend:
```

```nginx
# nginx.conf - Route to blue by default
upstream app {
    # Active environment (blue)
    server app-blue:3000;
    # server app-green:3000;  # Uncomment to switch
}

server {
    listen 80;

    location / {
        proxy_pass http://app;
        proxy_set_header Host $host;
    }

    # Health check endpoints for both
    location /health/blue {
        proxy_pass http://app-blue:3000/health;
    }

    location /health/green {
        proxy_pass http://app-green:3000/health;
    }
}
```

```bash
# deploy.sh - Blue-green deployment script
#!/bin/bash

NEW_VERSION=$1
CURRENT_ENV=$(curl -s localhost/health | jq -r '.env')

if [ "$CURRENT_ENV" == "blue" ]; then
    TARGET="green"
else
    TARGET="blue"
fi

echo "Deploying $NEW_VERSION to $TARGET environment"

# Update target environment
export ${TARGET^^}_VERSION=$NEW_VERSION
docker compose up -d app-$TARGET

# Wait for health check
until curl -sf localhost/health/$TARGET > /dev/null; do
    echo "Waiting for $TARGET to be healthy..."
    sleep 5
done

echo "Switching traffic to $TARGET"
# Swap nginx config and reload
sed -i "s/app-$CURRENT_ENV/app-$TARGET/g" nginx.conf
docker compose exec nginx nginx -s reload

echo "Deployment complete! Traffic now on $TARGET"
```
</details>

---

**Q50.** Design a Docker-based development environment that mirrors production but allows for:
- Hot reload for code changes
- Debug port access
- Local database seeding
- Service mocking for external APIs

<details>
<summary>Answer</summary>

```yaml
# docker-compose.yml (base)
version: '3.8'

services:
  api:
    build:
      context: ./api
      target: production
    environment:
      - DATABASE_URL=postgresql://postgres:secret@db:5432/app
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    networks:
      - backend

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=app
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend

  redis:
    image: redis:7-alpine
    networks:
      - backend

volumes:
  pgdata:

networks:
  backend:
```

```yaml
# docker-compose.override.yml (development - auto-loaded)
version: '3.8'

services:
  api:
    build:
      context: ./api
      target: development  # Use dev target with dev dependencies
    ports:
      - "3000:3000"       # API port
      - "9229:9229"       # Node.js debug port
    volumes:
      - ./api:/app                    # Hot reload
      - /app/node_modules             # Preserve container's node_modules
    environment:
      - NODE_ENV=development
      - DEBUG=app:*
      - EXTERNAL_API_URL=http://mock-api:3001  # Use mock
    command: npm run dev:debug        # Start with debugger
    depends_on:
      - db
      - redis
      - mock-api

  db:
    ports:
      - "5432:5432"                   # Access from host
    volumes:
      - ./dev/seed.sql:/docker-entrypoint-initdb.d/seed.sql

  # Mock external APIs
  mock-api:
    image: mockserver/mockserver
    ports:
      - "3001:1080"
    environment:
      - MOCKSERVER_INITIALIZATION_JSON_PATH=/config/init.json
    volumes:
      - ./dev/mocks:/config
    networks:
      - backend

  # Mail catcher for email testing
  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"   # SMTP
      - "8025:8025"   # Web UI
    networks:
      - backend
```

```dockerfile
# api/Dockerfile
# Development target
FROM node:18-alpine AS development
WORKDIR /app
COPY package*.json ./
RUN npm install  # Include devDependencies
COPY . .
CMD ["npm", "run", "dev"]

# Production target
FROM node:18-alpine AS production
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
USER node
CMD ["node", "dist/server.js"]
```

```json
// dev/mocks/init.json - MockServer configuration
[
  {
    "httpRequest": {
      "method": "GET",
      "path": "/api/external/users"
    },
    "httpResponse": {
      "statusCode": 200,
      "headers": {
        "Content-Type": "application/json"
      },
      "body": {
        "users": [
          {"id": 1, "name": "Test User"}
        ]
      }
    }
  }
]
```

```bash
# Usage:
# Development (uses override automatically)
docker compose up

# Production-like (skip override)
docker compose -f docker-compose.yml up

# Debug with VS Code:
# Add to .vscode/launch.json:
{
  "type": "node",
  "request": "attach",
  "name": "Docker: Attach",
  "port": 9229,
  "address": "localhost",
  "localRoot": "${workspaceFolder}/api",
  "remoteRoot": "/app"
}
```
</details>

---

## Answers Summary

| Level | Questions | Topics Covered |
|-------|-----------|----------------|
| 1. Beginner | Q1-Q10 | Basic concepts, simple commands |
| 2. Elementary | Q11-Q20 | Dockerfile basics, images, containers |
| 3. Intermediate | Q21-Q30 | Volumes, networks, Docker Compose |
| 4. Advanced | Q31-Q40 | Multi-stage, security, production |
| 5. Expert | Q41-Q50 | Architecture, CI/CD, orchestration |

---

*Practice these questions to solidify your Docker knowledge!*
