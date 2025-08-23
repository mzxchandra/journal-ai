# journal-ai

[DEPLOYED ON VERCEL](https://better-days.vercel.app/)

Web App helping elderly users journal. Uses API calls to Google's Gemma model to generate prompts and ask follow-up questions.

User Research, Wireframes, Requirements, and more:

https://docs.google.com/document/d/1JYy5xUIRkJ0YuyuS7xmED2MCLdpVG1jeFytnF_o_bFc/edit?usp=sharing


**Stack:**

Backend: Flask

Frontend: HTML

Other Tools: Google Vertex AI API

Deployed on: Vercel

## Database initialization

In production, the database tables are created separately. Run the setup once during deployment:

```
ENVIRONMENT=production python init_prod_db.py
```

Alternatively, trigger the `/init-db` endpoint with a POST request:

```
curl -X POST "https://<your-domain>/init-db?secret=$INIT_DB_SECRET"
```

This step should be executed once via your CI/CD pipeline or migration tool.
