# MLOps Command Reference

Since you're an AI engineer, this category bridges your ML background with the DevOps commands above — this is where they actually meet in a real job.

## Python Environment & Dependency Management

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip freeze > requirements.txt
pip install --upgrade pip
conda create -n myenv python=3.11
conda activate myenv
conda env export > environment.yml
poetry install
poetry add <package>
poetry lock
```

## Model Training Jobs (as k8s Jobs — bridges to the kubernetes category)

```
kubectl create job train-job --image=my-training-image -- python train.py
kubectl get jobs
kubectl logs job/train-job -f
kubectl describe job train-job
kubectl delete job train-job
```

## GPU-Related Commands

```
nvidia-smi
nvidia-smi -l 1
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
kubectl describe node <gpu-node> | grep -A5 "nvidia.com/gpu"
```

## MLflow (experiment tracking)

```
mlflow ui
mlflow run .
mlflow models serve -m runs:/<run-id>/model -p 5001
mlflow experiments list
mlflow runs list --experiment-id <id>
export MLFLOW_TRACKING_URI=http://localhost:5000
```

## DVC (Data Version Control)

```
dvc init
dvc add data/dataset.csv
dvc push
dvc pull
dvc status
dvc repro
dvc dag
dvc remote add -d storage s3://mybucket/dvcstore
```

## Model Serving

```
docker build -t model-server .
docker run -p 8501:8501 -v $(pwd)/model:/models/model tensorflow/serving
curl -X POST http://localhost:8501/v1/models/model:predict -d '{"instances": [[1,2,3]]}'
kubectl apply -f model-deployment.yaml
kubectl expose deployment model-server --port=8501
```

## Kubeflow / KServe-style commands (recognize these, common in production ML)

```
kubectl get inferenceservice
kubectl describe inferenceservice <name>
kubectl get pods -n kubeflow
kubectl apply -f pipeline.yaml
```

## Data & Pipeline Debugging

```
python -c "import pandas as pd; print(pd.read_csv('data.csv').info())"
python -m cProfile train.py
python -m memory_profiler train.py
jupyter nbconvert --to script notebook.ipynb
```

## Monitoring Model Performance in Production (bridges to monitoring category)

```
curl http://localhost:8000/metrics
kubectl top pod <model-serving-pod>
kubectl logs <model-serving-pod> --tail=100
```

PromQL for model-serving metrics:
```
rate(model_prediction_latency_seconds_sum[5m]) / rate(model_prediction_latency_seconds_count[5m])
model_prediction_errors_total
rate(model_requests_total[5m])
```

## Concepts worth knowing cold

- **Training/serving skew** — the classic ML production bug: preprocessing differs between training pipeline and serving pipeline, causing silent accuracy drops with zero errors or crashes
- **Model versioning** — never deploy a model without a version tag; you need instant rollback capability just like any other deployment
- **Data drift vs concept drift** — data drift is input distribution changing, concept drift is the relationship between input and output changing; both look like "the model got worse" but need different fixes
- **Canary deploys for models** — route 5% of traffic to the new model version, compare live metrics before full rollout, exactly like a canary code deploy
