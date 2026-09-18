<h2>How to use</h2>

1. Clone this repo.

```terminal
git clone https://github.com/baonguyengrrg/FCAJ-Buildrathon
```
2. Init environment.

```terminal 
docker compose up -d --build
./init-infra.sh
```

3. Config .env in your code project by replacing with your info.

```terminal
AWS_ENDPOINT_URL=http://localhost:8000
AWS_ACCESS_KEY_ID=ten-cua-ban
AWS_SECRET_ACCESS_KEY=dummy
AWS_DEFAULT_REGION=us-east-1
```
