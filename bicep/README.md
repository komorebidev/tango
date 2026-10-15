# bicep

* entra.bicep is separated because it needs to be deploy at tenant level
* Deploy main.bicep first and then entra.bicep

## Validation command for main.bicep

```powershell
az deployment sub validate --name tango-deployment --location japaneast --template-file main.bicep --parameters location=japaneast
```

## Validation command for entra.bicep

```powershell
$suffix = (az account show --query id -o tsv).Substring((az account show --query id -o tsv).Length - 4, 4)

az webapp show --name "tangoapp-$suffix" --resource-group "tango-$suffix" --query defaultHostName -o tsv

az deployment tenant validate --name tango-entra-deployment --location japaneast --template-file entra.bicep --parameters suffix=$suffix webAppHostName=$webAppHostName
```

## Run command for main.bicep
```powershell
az deployment sub create --name "tango-deployment" --location japaneast --template-file main.bicep --parameters location=japaneast --no-wait
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
