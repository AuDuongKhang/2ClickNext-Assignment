# Exhibition sales CRM

We'd like you to build a small CRM for a fictional company that designs and builds exhibition stands. The starter includes a database setup and a simulated export from its old system. You choose the application stack and how the product works.

You have **48 hours from receipt to submit**. You may spend as much of that time on the assignment as you choose. If parts are unfinished, note them in your README. AI tools are welcome. You don't need to buy anything.

## The sales team's problem

There are six people in sales, dealing with new enquiries, quotations and returning exhibitors. The same customer might need a stand at several fairs, or come back for next year's edition with a different budget and brief.

The account managers want everything about an exhibitor in one place. They don't want to enter a contact again for each fair. The sales coordinator wants this year's enquiry to show only this edition's conversations and follow-ups: people have been treating last year's agreement as if it still applied.

There's also disagreement about when technical should get involved. The sales director wants an enquiry passed over as soon as the customer names a fair and gives a budget. Waiting for the rest of the brief costs time. The technical coordinator wants nothing passed over until the stand area and requested height are known and checked against the fair information, because the team keeps starting work on requests it can't deliver.

Meanwhile, the account managers need to know who to call and what they're waiting for. If a customer promises to confirm the floor area on Friday, that needs to turn into something they can find and act on.

Build a first version that lets them:

- find an exhibitor or contact and see the relevant opportunities and fair editions;
- update an opportunity and record a customer conversation;
- schedule a follow-up and find it again later.

Use the supplied archive and save changes in PostgreSQL. Choose the screens and how to reconcile the team's requests. Explain the decisions briefly in your README. Plan for the archive to grow to 100,000 contacts, with the associated companies, opportunities and activities; everyday searches should remain practical at that size.

## The handoff assistant

Add an action on an opportunity to help sales prepare a brief for the technical team. It should gather the CRM and fair information, propose a next step, then check the proposal. Missing information and conflicting requests must affect the outcome, according to the handoff policy you've chosen.

Implement a small agent orchestration: one role prepares the brief, another checks it, and a coordinator decides whether to continue or stop. Ordinary functions in one process are fine. Use a deterministic local stand-in for model responses and label it as such. **No API keys, external model calls or model downloads.**

Save each run with the opportunity, including the information it used, the role outputs and the reason for the decision. We should be able to revisit it and run the assistant again after editing the brief. A chat interface, agent framework and automatic emails aren't needed.

## The export

The files and their format are described in [data/README.md](data/README.md). Choose your own database model and import the whole dataset, keeping the useful commercial information and relationships. Note any exclusions or ambiguous values you had to interpret.

**Do not change the source files or cut the dataset down to a sample.** Put transformations in the importer. Before review, we'll replace the entire `data/` folder with our original copy and run `./reset.sh` followed by `./dev.sh`. The import must work with that replacement. A solution that depends on edited files, a hard-coded subset or generated replacement records does not meet the requirement.

## Running it

Use PostgreSQL and run the entire application through `compose.yml`. The review versions, available resources and portability requirements are in [docs/environment.md](docs/environment.md). Build your application locally from the submitted source using Dockerfiles, and follow [docs/image-policy.md](docs/image-policy.md) for downloaded images.

Pin versions for images, runtimes and package managers. Use committed lockfiles and frozen installs where supported; otherwise use your ecosystem's equivalent dependency-pinning and reproducible-install mechanisms. Avoid `latest` and major-only versions where a more precise version is available; image digests are optional. Supply working local configuration so we don't have to fill in environment variables or configuration files.

We'll use these commands:

| Command               | Expected result                                                                                                                                                                                        |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `./dev.sh`            | Build and start everything, create the schema and import the data on first use. The app is available at `http://localhost:3000` without further commands. Staying in the foreground with logs is fine. |
| `docker compose down` | Stop the app and keep its data.                                                                                                                                                                        |
| `./reset.sh`          | Stop the app and remove this project's persistent data and resources. The next start imports the original archive again.                                                                               |
| `./verify.sh`         | Check Compose configuration and HTTP reachability after startup.                                                                                                                                       |

Later starts must keep user changes and must not duplicate the import. Reset must affect only this project; don't use global Docker cleanup.

You can change `compose.yml`, `dev.sh`, `reset.sh`, `README.md`, `.gitignore` and `.gitattributes`, and add your code, Dockerfiles, migrations, importer, tests and configuration.

Leave these files alone: **`ASSIGNMENT.md`, `verify.sh`, `data/`, `docs/environment.md` and `docs/image-policy.md`.** We replace them with original copies before reviewing your submission. Keep your implementation elsewhere so it still works after that replacement and a reset.

## What to send us

Create a public Git repository for your work. Keep your development history; we don't require a particular number of commits. Include everything needed to start from a clean clone. Check that the repository is accessible without signing in, and keep it available until the hiring process is complete. Do not commit credentials or private information.

Before the deadline, send an email using the exact recipients, subject format and field labels below. Replace the bracketed values with your details.

```text
To: giuseppe@2clicksolutions.com
Cc: alberto.canci@playgroundaps.it, info@nicolopadovan.com
Subject: Assignment submission - [First name] [Surname]

First name: [First name]
Surname: [Surname]
Email: [Your contact email]
Repository URL: [Public repository URL]
Commit hash: [Full commit hash to review]
Time spent: [Hours and minutes]
```

Push the commit before sending the email. Use `git rev-parse HEAD` to get its full hash. We will review that commit, not later changes on the branch. The email is your submission; pushing code alone does not count. Do not send code attachments or file-sharing links.

In the README, tell us the stack and versions, time spent, import decisions and unfinished work. Explain how you handled the team's competing requests and how to try the assistant with a complete and an incomplete enquiry. Short notes are enough. You don't need a public deployment or a video.

Assume one user with access to the archive. Leave login, permissions and billing out. This is a sales tool: you don't need to generate floor plans, 3D models, quotations or bills of materials, or issue technical approvals. The fair information we supply is enough; no industry research is needed. The scenario and data are fictional.

Send questions through the contact in your invitation. We'll share any answer that changes the assignment with everyone in the same hiring round.
