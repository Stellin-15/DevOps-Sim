# CI/CD Command Reference

## Git (the foundation of every CI/CD trigger)

```
git status
git add .
git commit -m "message"
git push origin <branch>
git pull
git fetch
git log --oneline
git diff
git branch
git checkout -b <branch>
git checkout <branch>
git merge <branch>
git rebase <branch>
git rebase -i HEAD~3
git cherry-pick <commit>
git tag v1.0.0
git tag -a v1.0.0 -m "release"
git push origin v1.0.0
git revert <commit>
git reset --hard <commit>
git stash
git stash pop
```

## GitHub Actions (workflow YAML — recognize this structure)

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install deps
        run: npm install
      - name: Run tests
        run: npm test
      - name: Build
        run: npm run build
      - name: Deploy
        if: github.ref == 'refs/heads/main'
        run: ./deploy.sh
```

## GitHub CLI

```
gh pr create
gh pr list
gh pr view <number>
gh pr merge <number>
gh pr checkout <number>
gh run list
gh run view <run-id>
gh run watch
gh workflow list
gh workflow run <workflow>
gh secret set <name>
```

## GitLab CI (.gitlab-ci.yml — recognize this structure)

```yaml
stages:
  - build
  - test
  - deploy

build-job:
  stage: build
  script:
    - docker build -t myapp .

test-job:
  stage: test
  script:
    - npm test

deploy-job:
  stage: deploy
  script:
    - ./deploy.sh
  only:
    - main
```

## Jenkins (Jenkinsfile — recognize this structure)

```groovy
pipeline {
    agent any
    stages {
        stage('Build') {
            steps { sh 'docker build -t myapp .' }
        }
        stage('Test') {
            steps { sh 'npm test' }
        }
        stage('Deploy') {
            when { branch 'main' }
            steps { sh './deploy.sh' }
        }
    }
}
```

## Deployment Strategies (concepts you'll be tested on in practice)

- **Rolling deployment** — replace instances gradually, some old/some new during rollout (default k8s Deployment behavior)
- **Blue-Green** — two full environments, switch traffic all at once, instant rollback by switching back
- **Canary** — release to a small % of traffic first, expand gradually if metrics look healthy
- **Feature flags** — ship code dark, toggle behavior without a redeploy

## Common pipeline debugging commands

```
gh run view <run-id> --log
gh run view <run-id> --log-failed
docker build --no-cache -t myapp .
docker run --rm myapp npm test
```

## Secrets & environment management in pipelines

```
gh secret set API_KEY --body "value"
gh secret list
export $(cat .env | xargs)
```

## Semantic versioning & tags (used constantly in release pipelines)

```
git tag -l
git describe --tags
git tag -d v1.0.0
git push origin --delete v1.0.0
```
