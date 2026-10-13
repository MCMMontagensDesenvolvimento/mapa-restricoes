'use client';
import {PublicClientApplication,type AccountInfo} from '@azure/msal-browser';

const tenant=process.env.NEXT_PUBLIC_ENTRA_TENANT_ID||'';
const clientId=process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID||'';
const apiScope=process.env.NEXT_PUBLIC_ENTRA_API_SCOPE||'';
export const entraConfigured=Boolean(tenant&&clientId&&apiScope);
export const msal=entraConfigured?new PublicClientApplication({auth:{clientId,authority:`https://login.microsoftonline.com/${tenant}`,redirectUri:process.env.NEXT_PUBLIC_APP_URL||globalThis.location?.origin,postLogoutRedirectUri:process.env.NEXT_PUBLIC_APP_URL||globalThis.location?.origin},cache:{cacheLocation:'sessionStorage'}}):null;
let initialized=false;
export async function initializeAuth(){if(msal&&!initialized){await msal.initialize();await msal.handleRedirectPromise();initialized=true}return msal}
export async function signIn(){const app=await initializeAuth();if(app)await app.loginRedirect({scopes:['openid','profile','email',apiScope]})}
export async function signOut(){const app=await initializeAuth();if(app)await app.logoutRedirect()}
export async function account():Promise<AccountInfo|null>{const app=await initializeAuth();return app?.getAllAccounts()[0]||null}
export async function accessToken(){const app=await initializeAuth();if(!app)return '';const a=app.getAllAccounts()[0];if(!a){await signIn();return ''}try{return(await app.acquireTokenSilent({account:a,scopes:[apiScope]})).accessToken}catch{await app.acquireTokenRedirect({account:a,scopes:[apiScope]});return ''}}

