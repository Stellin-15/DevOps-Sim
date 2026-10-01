# Identity and Secrets Command Reference

Source material for `scenarios/identity/`. Two questions run through all
of it: *who is this caller?* (tokens, OAuth and OIDC, certificates) and
*where do credentials live?* (Vault, external secret stores, encrypted
files in Git). Cloud IAM is in the AWS, Azure, and Google Cloud
categories; Kubernetes RBAC is in Kubernetes; finding leaked secrets is
in Security.

## JSON Web Tokens

```
echo "$TOKEN" | cut -d. -f1 | base64 -d | jq        # header: alg, kid
echo "$TOKEN" | cut -d. -f2 | base64 -d | jq        # claims: iss, sub, aud, exp, scope
date -d @<exp>                                      # expiry as a date
curl -s https://<issuer>/.well-known/openid-configuration | jq
curl -s https://<issuer>/.well-known/jwks.json | jq '.keys[].kid'
```

A JWT is signed, not encrypted: anyone holding it can read it. Check
`iss`, `aud`, `exp`, and the signature against the issuer's published
keys (JWKS), selected by `kid`.

## OAuth 2.0 and OpenID Connect

```
curl -s -X POST https://<issuer>/oauth/token \
     -d grant_type=client_credentials -d client_id=<id> -d client_secret=<secret> -d audience=<api>
curl -s -H "Authorization: Bearer $TOKEN" https://<api>/...
curl -s -H "Authorization: Bearer $TOKEN" https://<issuer>/userinfo
curl -s -X POST https://<issuer>/oauth/introspect -u <id>:<secret> -d token=$TOKEN
curl -s -X POST https://<issuer>/oauth/revoke -u <id>:<secret> -d token=$TOKEN
```

Flows: authorization code with PKCE (users, in browsers and apps), client
credentials (service to service), device code (CLIs and TVs). Implicit
and password grants are obsolete. Access tokens are short-lived; refresh
tokens get new ones.

## Kubernetes Identity

```
kubectl auth whoami
kubectl create token <serviceaccount> --duration=10m
kubectl get --raw /.well-known/openid-configuration
kubectl get --raw /openid/v1/jwks
kubectl exec <pod> -- cat /var/run/secrets/kubernetes.io/serviceaccount/token
```

## HashiCorp Vault

```
vault status
vault login -method=oidc
vault token lookup
vault secrets list            vault auth list
vault kv put secret/<path> key=value
vault kv get secret/<path>             vault kv get -field=<key> secret/<path>
vault kv get -version=<n> secret/<path>
vault kv metadata get secret/<path>
vault kv rollback -version=<n> secret/<path>
vault policy write <name> <file.hcl>    vault policy read <name>
vault token capabilities <path>
vault read database/creds/<role>        # a new, short-lived database user
vault lease lookup <lease_id>
vault lease revoke <lease_id>           vault lease revoke -prefix database/creds/<role>
vault operator unseal                   vault operator raft list-peers
vault audit list
```

```
path "secret/data/shop/*" {
  capabilities = ["read"]
}
```

## Secrets in Kubernetes and Git

```
kubectl get externalsecret -A           kubectl describe externalsecret <name>
kubectl get secretstore,clustersecretstore
kubectl get secret <name> -o jsonpath='{.data.<key>}' | base64 -d
kubectl rollout restart deployment/<name>
kubeseal --format yaml < secret.yaml > sealedsecret.yaml
sops -e -i secrets.yaml                 sops -d secrets.yaml
sops updatekeys secrets.yaml
age-keygen -o key.txt
```

## PKI and Mutual TLS

```
openssl genrsa -out client.key 2048
openssl req -new -key client.key -subj "/CN=<name>" -out client.csr
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 30 -out client.crt
openssl verify -CAfile ca.crt client.crt
openssl x509 -in <cert> -noout -subject -issuer -dates
openssl x509 -in <cert> -noout -ext subjectAltName
curl --cacert ca.crt --cert client.crt --key client.key https://<host>/
openssl s_client -connect <host>:443 -cert client.crt -key client.key -CAfile ca.crt
```

## cert-manager

```
kubectl get certificate -A
kubectl describe certificate <name>
kubectl get certificaterequest,order,challenge -n <ns>
kubectl describe challenge <name> -n <ns>
kubectl get clusterissuer
cmctl status certificate <name> -n <ns>
cmctl renew <name> -n <ns>
```
