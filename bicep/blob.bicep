targetScope = 'resourceGroup'

@description('Azure region for the storage account.')
param location string

@description('Suffix derived from the subscription ID.')
param suffix string

@description('Principal ID of the Tango App Service managed identity.')
param webAppPrincipalId string

var storageAccountName = 'tangodata${suffix}'
var containerName = 'tango-data'
var blobContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(container.id, webAppPrincipalId, blobContributorRoleId)
  scope: container
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      blobContributorRoleId
    )
    principalId: webAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output storageAccountName string = storageAccount.name
output storageAccountUrl string = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}'
output containerName string = container.name