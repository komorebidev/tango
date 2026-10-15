# bicep

* entra.bicep is separated because it needs to be deploy at tenant level
* Deploy main.bicep first and then entra.bicep

## Important Note

### Troubleshooting: Bicep Microsoft Graph Deployment Error (`403 Forbidden`)

Even as a Global Admin, deploying Bicep files that use Microsoft Graph from Cloud Shell fails with a `403 Forbidden` error because Cloud Shell's default session uses an Azure token instead of a Microsoft Graph token.

**The Fix (Azure CLI in Cloud Shell):**
```bash
az login --scope [https://graph.microsoft.com/.default](https://graph.microsoft.com/.default)
```

## Run commands

### Get subscription suffix

```powershell
$subscriptionId = az account show --query id -o tsv
$suffix = $subscriptionId.Substring($subscriptionId.Length - 4, 4)
```

### Get Entra tenant ID

```powershell
$entraTenantId = az account show --query tenantId -o tsv
```

### Get Entra app registration client ID

```powershell
$entraClientId = az ad app list --display-name "tango-auth-$suffix" --query "[0].appId" -o tsv
```

### Get App Service hostname
```powershell
$webAppHostName = az webapp show --name "tangoapp-$suffix" --resource-group "tango-$suffix" --query defaultHostName -o tsv
```

### Validate main.bicep

```powershell
az deployment sub validate --name tango-deployment --location japaneast --template-file main.bicep --parameters location=japaneast entraClientId=$entraClientId entraTenantId=$entraTenantId
```

### Validate entra.bicep
```powershell
az deployment tenant validate --name tango-entra-validation --location japaneast --template-file entra.bicep --parameters suffix=$suffix webAppHostName=$webAppHostName
```

### Deploy main.bicep
```powershell
az deployment sub create --name tango-deployment --location japaneast --template-file main.bicep --parameters location=japaneast entraClientId=$entraClientId entraTenantId=$entraTenantId --no-wait
```

### Deploy entra.bicep only when the app registration itself needs updating

```powershell
az deployment tenant create --name tango-entra-deployment --location japaneast --template-file entra.bicep --parameters suffix=$suffix webAppHostName=$webAppHostName
```

### Package zip command

* Inside the package directory (flask files)

```python
Set-Location "xxxapp"

@'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path.cwd()
output = root.parent / "tangoapp.zip"

files = [
    "app.py",
    "cloudflare_ai.py",
    "requirements.txt",
    "templates/style.css",
    "templates/app.js",
    "templates/add_vocabulary.html",
    "templates/index.html",
]

with ZipFile(output, "w", ZIP_DEFLATED) as z:
    for name in files:
        z.write(root / name, arcname=name)

print(f"Created {output}")
'@ | python -
```

### Flask deployment command

```powershell
$subId = az account show --query id --output tsv
$suffix = $subId.Substring($subId.Length - 4)
$rg = "tango-$suffix"
$app = "tangoapp-$suffix"

az webapp deploy `
  --resource-group $rg `
  --name $app `
  --src-path ".\tangoapp.zip" `
  --type zip
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
