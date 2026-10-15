targetScope = 'subscription'

@description('Azure region for the resource group and application.')
param location string = 'japaneast'

@description('Application (client) ID of the Entra app registration.')
param entraClientId string

@description('Tenant ID of the Entra directory.')
param entraTenantId string

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
    entraClientId: entraClientId
    entraTenantId: entraTenantId
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

output resourceGroupName string = rg.name
output webAppName string = flask.outputs.webAppName
output webAppUrl string = flask.outputs.webAppUrl
output storageAccountName string = blob.outputs.storageAccountName
output storageAccountUrl string = blob.outputs.storageAccountUrl
output storageContainerName string = blob.outputs.containerName