# model-comparer

Run app
```
docker compose up --build
```

Install models
```
docker compose exec ollama ollama pull llama3:latest
docker compose exec ollama ollama pull mistral:latest
docker compose exec ollama ollama pull gemma:2b
```

Verify models correctly installed
```
curl http://localhost:11434/api/tags
docker compose exec ollama ollama list
```

Test model prompt
```
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3", "prompt": "Hello"}'
```
