# Deployment guide: free demo, GCP and AWS

This guide deploys the API container (`Dockerfile`) with a managed PostgreSQL database that has pgvector.
The same image runs everywhere. Only the database URL and the secrets change.

| Option | Cost | Use it for |
|---|---|---|
| [Free demo: Render + Neon](#free-demo-render--neon) | $0 | Demos and a shareable link, with sample or public documents only |
| [GCP: Cloud Run + Cloud SQL](#gcp-cloud-run--cloud-sql-for-postgresql) | Paid | Client pilots and production |
| [AWS: ECS Fargate + RDS](#aws-ecs-fargate--rds-for-postgresql) | Paid | Client pilots and production |

```
Client ──HTTPS──▶ API container (FastAPI, port 8000) ──▶ Managed PostgreSQL + pgvector
                          │
                          └──▶ Gemini / OpenAI API
```

## Before you start (all options)

1. **The image works locally.** `docker compose up -d --build`, then open <http://localhost:8000/docs>.
2. **Build for x86-64.** Cloud Run and Fargate run `linux/amd64` by default. On an Apple Silicon Mac, add
   `--platform linux/amd64` to `docker build`.
3. **Decide the settings.** They are the same environment variables as in `.env.example`:

   | Variable | Production value |
   |---|---|
   | `AI_PROVIDER`, `EMBEDDING_MODEL`, `LLM_MODEL` | Same as the ones you evaluated with |
   | `GOOGLE_API_KEY` or `OPENAI_API_KEY` | **Secret** (Secrets Manager / Secret Manager), never a plain env var |
   | `DATABASE_URL` | **Secret**: it contains the database password |
   | `SERVICE_API_KEY` | **Secret**: a long random string. Callers send it as the `X-API-Key` header. Without it the API is open to anyone. |
   | `LLM_REQUESTS_PER_MINUTE` | `0` on paid plans, `5` on the Gemini free tier |

4. **Understand where documents live.** The *index* (chunks and vectors) lives in PostgreSQL and survives
   restarts and redeploys. The *PDF files* live in the container's `data/pdfs` folder, and container disks
   on Cloud Run and Fargate are **temporary**. So:
   - **Recommended:** put the client's PDFs in `data/pdfs` **before building the image**, then run ingestion
     once as a one-off job (steps below). Redeploying doesn't touch the index.
   - `POST /documents` uploads work, but the uploaded file disappears when the container restarts. The chunks
     that are already ingested stay in the database. Run `POST /ingest` only while all PDFs are present,
     because ingestion rebuilds the collection from the files it can see.
   - Persistent uploads (S3 / Cloud Storage) are a planned improvement.

Generate a service key with, for example, `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

---

## Free demo: Render + Neon

A public demo link that costs nothing. **Not for client documents and not for production**: see
[Limits of the free setup](#limits-of-the-free-setup).

| Part | Service | Notes |
|---|---|---|
| API container | [Render](https://render.com) free web service | Builds the `Dockerfile` straight from GitHub |
| PostgreSQL + pgvector | [Neon](https://neon.com) free plan | pgvector is included |
| AI | Gemini free tier ([get a key](https://aistudio.google.com/apikey)) | Rate-limited |

Don't use Render's own free PostgreSQL: it is deleted after 30 days.

### 1. Database (Neon)

1. Create a Neon project in the region closest to your users. For India, choose **AWS Asia Pacific
   (Singapore)**, which matches Render's Singapore region.
2. Click **Connect**, turn **Connection pooling** off and copy the connection string. A demo needs only a few
   connections, and the direct connection behaves exactly like the local database.
3. Change only the start of the URL, from `postgresql://` to `postgresql+psycopg://`, and keep the parameters:
   `postgresql+psycopg://neondb_owner:PASSWORD@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`

The pipeline enables pgvector itself.

### 2. Build the index from your laptop

Render's free instances have no shell and no one-off jobs, so run ingestion locally against Neon. A real
environment variable wins over `.env`, so only `DATABASE_URL` changes. The provider, models and API key still
come from your `.env`.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://neondb_owner:PASSWORD@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
python -m rag_pipeline.cli ingest
python -m rag_pipeline.cli status
Remove-Item Env:DATABASE_URL     # back to the local database
```

On macOS or Linux: `DATABASE_URL="postgresql+psycopg://..." python -m rag_pipeline.cli ingest`.

Ingest the same PDFs that are committed in `data/pdfs`. The image Render builds contains those files, and a
`POST /ingest` on the server rebuilds the index from them.

### 3. API service (Render)

1. **New → Web Service**, connect GitHub and choose this repository. If the repository belongs to a GitHub
   organization, an organization owner may need to approve Render's GitHub app.
2. Settings:
   - Language: **Docker** (detected from the `Dockerfile`)
   - Branch: `main`. Every push to it redeploys.
   - Region: **Singapore** (same as the database)
   - Instance type: **Free**
   - Health Check Path (under **Advanced**): `/health`
3. Environment variables:

   | Variable | Value |
   |---|---|
   | `AI_PROVIDER` | `gemini` |
   | `GOOGLE_API_KEY` | Your Gemini key |
   | `EMBEDDING_MODEL` | **The same model you ingested with** (`gemini-embedding-001`). Otherwise queries refuse to run. |
   | `LLM_MODEL` | `gemini-2.5-flash-lite` |
   | `LLM_REQUESTS_PER_MINUTE` | `5` |
   | `DATABASE_URL` | The Neon URL from step 1 |
   | `SERVICE_API_KEY` | A long random string (see above). **Never leave it empty on a public URL.** |
   | `PORT` | `8000`, so Render and the image's built-in health check use the same port |

4. **Deploy Web Service.** The first build takes a few minutes.

Render stores environment variables encrypted. That is acceptable for a demo; production keeps secrets in a
secret manager, as in the GCP and AWS sections.

### 4. Verify

Open `https://YOUR-SERVICE.onrender.com/docs`, click **Authorize**, paste the `SERVICE_API_KEY` and try
`POST /ask`. Or from PowerShell:

```powershell
$URL = "https://YOUR-SERVICE.onrender.com"
Invoke-RestMethod "$URL/health"
Invoke-RestMethod "$URL/ask" -Method Post -ContentType "application/json" `
  -Headers @{ "X-API-Key" = "YOUR-SERVICE-KEY" } `
  -Body '{"question": "What is the notice period after probation?"}'
```

**Update after a change:** push to `main` and Render rebuilds and redeploys. If the PDFs or `EMBEDDING_MODEL`
changed, re-run step 2 as well.

### Limits of the free setup

Checked in October 2026. Free plans change, so confirm on the providers' pricing pages.

- **Sleeps when idle.** The API spins down after 15 minutes without requests, and the next request waits
  about a minute while it starts. Open `/health` shortly before a demo. The 750 free instance hours per
  workspace per month cover one service running all month.
- **512 MB of memory.** The API calls hosted models and runs none itself, so it is expected to fit. If the
  Render logs show out-of-memory restarts, move to a paid instance.
- **Temporary disk.** PDFs uploaded with `POST /documents` disappear whenever the service restarts or
  sleeps. Add and remove documents by changing `data/pdfs` in git and re-running step 2, not through the
  live API.
- **Database size.** Neon's free plan includes 1 GB per project. A 3072-dimension Gemini vector takes about
  12 KB, so that holds tens of thousands of chunks. Neon suspends the database when idle and wakes it
  automatically on the next connection.
- **Gemini free tier.** It is rate-limited, and Google may use free-tier prompts and documents to improve its
  products. **Use only sample or public documents.** For a client pilot, use a paid key and the GCP or AWS
  setup below.
- **Not production-grade.** The database accepts connections from the internet (protected by password and
  TLS only), and neither free plan comes with an uptime guarantee.

---

## GCP: Cloud Run + Cloud SQL for PostgreSQL

Cloud SQL for PostgreSQL supports pgvector. The pipeline enables it itself with
`CREATE EXTENSION IF NOT EXISTS vector`.

```bash
PROJECT=my-project
REGION=asia-south1
INSTANCE=rag-db
IMAGE=$REGION-docker.pkg.dev/$PROJECT/rag/rag-pipeline-service:v1

gcloud config set project $PROJECT
gcloud services enable run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com \
    secretmanager.googleapis.com

# 1. Database (PostgreSQL 16). Pick a larger tier for production.
gcloud sql instances create $INSTANCE --database-version=POSTGRES_16 --region=$REGION \
    --tier=db-g1-small --edition=ENTERPRISE
gcloud sql databases create ragdb --instance=$INSTANCE
gcloud sql users set-password postgres --instance=$INSTANCE --password='CHANGE-ME'

# 2. Image
gcloud artifacts repositories create rag --repository-format=docker --location=$REGION
gcloud auth configure-docker $REGION-docker.pkg.dev
docker build --platform linux/amd64 -t $IMAGE .
docker push $IMAGE

# 3. Secrets. Cloud Run connects to Cloud SQL through a Unix socket under /cloudsql/.
CONN=$(gcloud sql instances describe $INSTANCE --format='value(connectionName)')
printf '%s' "postgresql+psycopg://postgres:CHANGE-ME@/ragdb?host=/cloudsql/$CONN" | \
    gcloud secrets create rag-database-url --data-file=-
printf '%s' "YOUR-GEMINI-KEY" | gcloud secrets create rag-google-api-key --data-file=-
printf '%s' "YOUR-SERVICE-KEY" | gcloud secrets create rag-service-api-key --data-file=-
# Allow Cloud Run's service account to read them (the default compute service account is used here).
SA=$(gcloud projects describe $PROJECT --format='value(projectNumber)')-compute@developer.gserviceaccount.com
for s in rag-database-url rag-google-api-key rag-service-api-key; do
  gcloud secrets add-iam-policy-binding $s --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor
done
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=roles/cloudsql.client

# 4. One-off ingestion job (re-run it whenever the PDFs change)
gcloud run jobs create rag-ingest --image=$IMAGE --region=$REGION \
    --command=python --args=-m,rag_pipeline.cli,ingest \
    --set-cloudsql-instances=$CONN \
    --set-env-vars=AI_PROVIDER=gemini,EMBEDDING_MODEL=gemini-embedding-001,LLM_MODEL=gemini-2.5-flash-lite \
    --set-secrets=DATABASE_URL=rag-database-url:latest,GOOGLE_API_KEY=rag-google-api-key:latest
gcloud run jobs execute rag-ingest --region=$REGION --wait

# 5. API service
gcloud run deploy rag-api --image=$IMAGE --region=$REGION --allow-unauthenticated \
    --add-cloudsql-instances=$CONN --memory=1Gi --min-instances=0 --max-instances=3 \
    --set-env-vars=AI_PROVIDER=gemini,EMBEDDING_MODEL=gemini-embedding-001,LLM_MODEL=gemini-2.5-flash-lite \
    --set-secrets=DATABASE_URL=rag-database-url:latest,GOOGLE_API_KEY=rag-google-api-key:latest,SERVICE_API_KEY=rag-service-api-key:latest
```

`--allow-unauthenticated` makes the URL reachable. Access is controlled by `SERVICE_API_KEY`. Cloud Run
sets `PORT` itself, and the container listens on it.

**Verify:**

```bash
URL=$(gcloud run services describe rag-api --region=$REGION --format='value(status.url)')
curl $URL/health
curl -X POST $URL/ask -H "X-API-Key: YOUR-SERVICE-KEY" -H "Content-Type: application/json" \
     -d '{"question": "What is the notice period after probation?"}'
```

**Update after a code or document change:** build and push a new tag, run
`gcloud run jobs update rag-ingest --image=NEW` and execute it (only if documents or the embedding model
changed), then `gcloud run deploy rag-api --image=NEW ...`.

---

## AWS: ECS Fargate + RDS for PostgreSQL

RDS for PostgreSQL 16 includes pgvector. The pipeline enables it itself.

### 1. Database (RDS)

Create it in the console (**RDS → Create database**) or with the CLI:

```bash
aws rds create-db-instance --db-instance-identifier rag-db --engine postgres --engine-version 16 \
    --db-instance-class db.t4g.small --allocated-storage 20 \
    --master-username postgres --master-user-password 'CHANGE-ME' --db-name ragdb \
    --no-publicly-accessible --vpc-security-group-ids sg-DB
```

- Put it in the same VPC as the ECS service. The database security group (`sg-DB`) allows port 5432 **only**
  from the ECS tasks' security group.
- RDS requires TLS, so add `sslmode=require` to the URL:
  `postgresql+psycopg://postgres:CHANGE-ME@rag-db.xxxx.REGION.rds.amazonaws.com:5432/ragdb?sslmode=require`

### 2. Image (ECR)

```bash
REGION=ap-south-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/rag-pipeline-service

aws ecr create-repository --repository-name rag-pipeline-service --region $REGION
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
docker build --platform linux/amd64 -t $REPO:v1 .
docker push $REPO:v1
```

### 3. Secrets (Secrets Manager)

```bash
aws secretsmanager create-secret --name rag/database-url   --secret-string 'postgresql+psycopg://...?sslmode=require'
aws secretsmanager create-secret --name rag/google-api-key --secret-string 'YOUR-GEMINI-KEY'
aws secretsmanager create-secret --name rag/service-api-key --secret-string 'YOUR-SERVICE-KEY'
```

The ECS **task execution role** needs `secretsmanager:GetSecretValue` on these three secrets.

### 4. ECS service

1. **ECS → Clusters → Create** a Fargate cluster.
2. **Task definition** (Fargate, 0.5 vCPU / 1 GB is enough for the API):
   - Image `$REPO:v1`, container port `8000`.
   - Environment: `AI_PROVIDER`, `EMBEDDING_MODEL`, `LLM_MODEL`.
   - Secrets ("ValueFrom" = secret ARN): `DATABASE_URL`, `GOOGLE_API_KEY` (or `OPENAI_API_KEY`),
     `SERVICE_API_KEY`.
   - Log driver `awslogs` (CloudWatch).
3. **Service** with an **Application Load Balancer**: listener HTTPS 443 (certificate from ACM), target
   group port 8000, health check path **`/health`**.
4. **Ingest once:** *Run new task* with the same task definition and the container command overridden to
   `python,-m,rag_pipeline.cli,ingest`. Re-run it whenever the PDFs or the embedding model change.

**Verify:** `curl https://YOUR-ALB-DOMAIN/health`, then the same `/ask` request as in the GCP section.

---

## Production checklist

- [ ] `SERVICE_API_KEY` is set, and all keys and the database URL come from a secret manager
- [ ] The database isn't publicly reachable; only the API can connect to it
- [ ] HTTPS in front of the API (Cloud Run does this automatically; on AWS use an ALB + ACM certificate)
- [ ] The evaluation (`python evaluation/evaluate.py`) passes with the **production** provider and models,
      run against the production index (for example as a one-off job with the command overridden)
- [ ] Database backups are enabled (on by default for Cloud SQL and RDS)
- [ ] Logs are visible (Cloud Logging / CloudWatch) and an uptime check calls `/health`
- [ ] Model and API costs are understood: every question = 1 embedding call + 1 chat call
