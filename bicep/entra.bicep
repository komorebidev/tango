targetScope = 'tenant'

extension microsoftGraphV1

@description('Suffix derived from the subscription ID.')
param suffix string

@description('The deployed Tango web app hostname.')
param webAppHostName string

var appDisplayName = 'tango-auth-${suffix}'
var appUniqueName = 'tango-auth-${suffix}'

resource appRegistration 'Microsoft.Graph/applications@v1.0' = {
  uniqueName: appUniqueName
  displayName: appDisplayName
  signInAudience: 'AzureADMyOrg'
  web: {
    homePageUrl: 'https://${webAppHostName}'
    redirectUris: [
      'https://${webAppHostName}/.auth/login/aad/callback'
    ]
  }
}

resource servicePrincipal 'Microsoft.Graph/servicePrincipals@v1.0' = {
  appId: appRegistration.appId
}

output applicationName string = appRegistration.displayName
output clientId string = appRegistration.appId
output servicePrincipalId string = servicePrincipal.id
output tenantId string = tenant().tenantId