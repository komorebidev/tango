targetScope = 'resourceGroup'

@description('Azure region for the web app.')
param location string

@description('Suffix derived from the subscription ID.')
param suffix string

@description('Resource ID of the App Service Plan.')
param appServicePlanId string

@description('Application (client) ID of the Entra app registration.')
param entraClientId string

@description('Tenant ID of the Entra directory.')
param entraTenantId string

var webAppName = 'tangoapp-${suffix}'
var storageAccountName = 'tangodata${suffix}'

resource webApp 'Microsoft.Web/sites@2024-04-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    httpsOnly: true
    serverFarmId: appServicePlanId
    reserved: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      alwaysOn: false
      appCommandLine: 'gunicorn --bind=0.0.0.0:8000 --timeout 600 app:app'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        { 
          name: 'GITHUB_REPOSITORY'
          value: 'komorebidev/tango' 
        }
        { 
          name: 'GITHUB_BRANCH'
          value: 'main'
          }
        { 
          name: 'GITHUB_DB_PATH'
          value: 'db.json'
          }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'PYTHONUNBUFFERED'
          value: '1'
        }
        {
          name: 'GITHUB_TOKEN'
          value: ''
        }
        {
          name: 'CLOUDFLARE_ACCOUNT_ID'
          value: ''
        }
        {
          name: 'CLOUDFLARE_API_TOKEN'
          value: ''
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_URL'
          value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
        }
        {
          name: 'AZURE_STORAGE_CONTAINER_NAME'
          value: 'tango-data'
        }
      ]
    }
  }
}

resource webAppAuth 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: webApp
  name: 'authsettingsV2'
  properties: {
    platform: {
      enabled: true
      runtimeVersion: '~1'
    }
    globalValidation: {
      requireAuthentication: false
      unauthenticatedClientAction: 'AllowAnonymous'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          openIdIssuer: 'https://login.microsoftonline.com/${entraTenantId}/v2.0'
          clientId: entraClientId
        }
        validation: {
          allowedAudiences: [
            entraClientId
          ]
        }
      }
    }
    login: {
      tokenStore: {
        enabled: false
      }
    }
  }
}

output webAppName string = webApp.name
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output webAppHostName string = webApp.properties.defaultHostName
output webAppPrincipalId string = webApp.identity.principalId