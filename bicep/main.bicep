targetScope = 'subscription'

@description('Azure region for the resource group and application.')
param location string = 'japaneast'

var suffix = substring(subscription().id, length(subscription().id) - 4, 4)
var resourceGroupName = 'tango-${suffix}'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
}

module servicePlan './serviceplan.bicep' = {
  scope: rg
  name: 'serviceplan-deployment'
  params: {
    location: location
    suffix: suffix
  }
}

module flask './flask.bicep' = {
  scope: rg
  name: 'flask-deployment'
  params: {
    location: location
    suffix: suffix
    appServicePlanId: servicePlan.outputs.appServicePlanId
  }
}

module blob './blob.bicep' = {
  scope: rg
  name: 'blob-deployment'
  params: {
    location: location
    suffix: suffix
    webAppPrincipalId: flask.outputs.webAppPrincipalId
  }
}

module entra './entra.bicep' = {
  scope: tenant()
  name: 'entra-deployment'
  params: {
    suffix: suffix
    webAppHostName: flask.outputs.webAppHostName
  }
}

output resourceGroupName string = rg.name
output webAppName string = flask.outputs.webAppName
output webAppUrl string = flask.outputs.webAppUrl
output storageAccountName string = blob.outputs.storageAccountName
output storageAccountUrl string = blob.outputs.storageAccountUrl
output storageContainerName string = blob.outputs.containerName
output entraClientId string = entra.outputs.clientId
output entraTenantId string = entra.outputs.tenantId