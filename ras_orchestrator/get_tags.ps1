$response = Invoke-RestMethod -Uri "https://hub.docker.com/v2/repositories/bitnami/mlflow/tags/?page_size=20"
$response.results | ForEach-Object { $_.name }