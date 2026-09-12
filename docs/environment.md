# Review environment

| Tool | Version |
|---|---|
| Docker Engine | 29.8.0 |
| Docker CLI | 29.8.0 |
| Docker Compose | 5.5.1 |
| Google Chrome | 153.0.8010.36 Stable |

Docker will have at least 4 CPUs and 8 GB RAM available, and port 3000 will be free. Setup can download images and dependencies. Once started, the app must work without external services, credentials or paid accounts.

Run all services as Linux containers. Images must support both `linux/amd64` and `linux/arm64`. Don't hard-code an architecture in Compose or Dockerfiles. Portable cross-compilation using Docker's build and target platform variables is allowed, provided the resulting application runs on either target architecture. Don't rely on the host operating system or its filesystem conventions.

Apart from the shell used by the supplied scripts and the review tools above, don't require software on the host. That includes application runtimes, package managers, Python, Node, `curl` and `jq`.
