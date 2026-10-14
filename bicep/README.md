# bicep

* Deployment for website infra

## Run command
```powershell
az deployment sub create `
  --name "tango-deployment" `
  --location japaneast `
  --template-file main.bicep `
  --parameters location=japaneast `
  --no-wait
```
## Check service plan tier

* Make sure it is free tier

```powershell
az appservice plan list --query "[].{Name:name, ResourceGroup:resourceGroup, Location:location, Tier:sku.tier, SKU:sku.name, Capacity:sku.capacity}" -o table
```

## Cleanup

```powershell
az group delete -n tango-d3c0 --yes --no-wait
```
