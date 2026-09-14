# Terraform-managed GameWorld Fleet pool

`main.tf` is the capacity authority for the stable `gameworld-autoresearch`
pool. Campaign workers claim from this pool; they do not create or mutate pool
or template resources through the SDK.

The pool uses the pinned public GameWorld image with anonymous image pulls,
gVisor, 4 CPUs, 16 GiB memory, and claim-driven autoscaling with minimum `0`,
initial `0`, and maximum `20`. The auto-research controller still limits
itself to two concurrent desktops.

Credentials remain outside Terraform configuration and state:

```bash
export CYCLOPS_ENDPOINT=https://run.cua.ai
export CYCLOPS_TOKEN_URL=https://auth.cua.ai/realms/cyclops-cs/protocol/openid-connect/token
export CYCLOPS_CLIENT_ID="$CUA_CLIENT_ID"
export CYCLOPS_CLIENT_SECRET="$CUA_CLIENT_SECRET"
```

Keep state outside the repository:

```bash
terraform -chdir=infra/fleet init
terraform -chdir=infra/fleet apply \
  -state=/home/node/.local/state/gameworld-autoresearch/fleet-terraform/terraform.tfstate
```

Provider `0.3.0` intentionally leaves an omitted `image_pull_secret` unset, so
the public GameWorld image is pulled anonymously without a Terraform
`dev_overrides` configuration.

Do not run `terraform destroy` as campaign cleanup. A campaign releases only
its named claims. The stable pool remains Terraform-owned and may scale to zero
according to its autoscaling policy; the user waived an explicit post-release
scale-to-zero observation.
