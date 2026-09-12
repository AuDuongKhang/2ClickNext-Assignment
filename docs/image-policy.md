# Container images

Build the application from the source in your repository. Downloaded images are fine for base images, language and build tools, and infrastructure such as PostgreSQL. Don't download a prebuilt application.

Use Docker Official Images (for example `node`, `python` or `postgres` from `docker.io/library/`) or these upstream sources:

- `mcr.microsoft.com/dotnet/`
- `ghcr.io/astral-sh/uv`
- `docker.io/oven/bun`
- `docker.io/denoland/deno`
- `gcr.io/distroless/`

If you need another image maintained by the software's own project, ask before submission. We'll share approved additions with the whole candidate group. Personal images, generic third-party images, private registries and registries requiring login aren't allowed.

Use a specific version tag or SHA-256 digest for every downloaded image. Don't use untagged images, `latest`, moving channel or distro aliases, or major-only tags. For a service built locally, Compose's `image` field can be the name of the build output.
