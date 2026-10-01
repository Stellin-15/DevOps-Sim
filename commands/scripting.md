# Scripting and Automation Command Reference

Source material for `scenarios/scripting/`. Bash scripting is in the
Linux category and its Writing Labs. This file covers the next layer:
Python as the automation language, the data tools every pipeline leans
on (jq, yq, regular expressions), Makefiles, and enough Go to build and
test the tools you'll run.

## Python Environments

```
python3 --version                 which python3
python3 -m venv .venv             source .venv/bin/activate        deactivate
python -m pip install -r requirements.txt
python -m pip install 'requests>=2.31,<3'
python -m pip list --outdated     python -m pip show <package>
python -m pip freeze > requirements.txt
pip-compile requirements.in       # pinned, hashed requirements.txt from loose inputs
uv venv      uv pip install -r requirements.txt      uv run script.py
pipx install <tool>               # a CLI tool in its own environment
```

## Running and Debugging Scripts

```
python script.py --help
echo $?                           # exit status of the last command
python -m pdb script.py           # breakpoint() in the code does the same
python -X faulthandler script.py
python -c "import sys; print(sys.path)"
LOG_LEVEL=DEBUG python script.py
/usr/bin/time -v python script.py      # peak memory (Maximum resident set size)
```

## Tests and Linters

```
pytest -q            pytest -x            pytest -k <expr>         pytest --lf
pytest --cov=<pkg> --cov-report=term-missing
ruff check .         ruff check --fix .   ruff format --check .
mypy <pkg>
```

## jq

```
jq '.items | length'
jq -r '.items[].metadata.name'
jq -r '.items[] | select(.status.phase != "Running") | .metadata.name'
jq '.[] | {name: .name, cpu: .resources.cpu}'
jq 'map(.price) | add'
jq 'group_by(.status) | map({status: .[0].status, count: length})'
jq -r '.[] | [.name, .status] | @tsv'
jq --arg env prod '.[] | select(.env == $env)'
jq -e '.tag'                      # non-zero exit if the result is null or false
jq 'keys'            jq 'paths'            jq '.. | .image? // empty'
```

## yq

```
yq '.spec.replicas' deployment.yaml
yq -i '.image.tag = "1.8.3"' values.yaml
yq '.spec.template.spec.containers[].image' deployment.yaml
yq -o=json '.' values.yaml        yq -P '.' data.json
yq eval-all 'select(.kind == "Deployment") | .metadata.name' all.yaml
yq '. *= load("override.yaml")' base.yaml
```

## Regular Expressions

```
grep -E '^(ERROR|FATAL)' app.log
grep -oE '[0-9]{1,3}(\.[0-9]{1,3}){3}' access.log          # just the matching part
grep -P 'duration=\K[0-9]+' app.log
sed -E 's/password=[^ ]+/password=REDACTED/g' app.log
sed -nE 's/.*status=([0-9]+).*/\1/p' app.log
```

Anchors `^ $`, classes `[a-z] \d \s`, quantifiers `* + ? {n,m}`,
groups `( )`, alternation `|`. Quantifiers are greedy by default.

## Makefiles

```
make            make <target>        make -n <target>       # dry run
make deploy ENV=prod
make -j4        make -B
```

```
.PHONY: test build
test:
	pytest -q
build: test
	docker build -t shop:$(VERSION) .
```

Recipe lines start with a tab, not spaces.

## Go for Operators

```
go version           go env GOOS GOARCH
go build ./...       go build -o bin/tool ./cmd/tool
go test ./...        go test -run TestName -v ./pkg/...      go test -race ./...
go vet ./...
go mod tidy          go mod download          go list -m all
GOOS=linux GOARCH=arm64 go build -o bin/tool-linux-arm64 ./cmd/tool
go run ./cmd/tool --help
```
