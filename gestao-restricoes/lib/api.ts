import {accessToken,entraConfigured} from './auth';
export function apiBase(){
 const configured=process.env.NEXT_PUBLIC_API_URL;
 if(configured)return configured.replace(/\/$/,'');
 if(typeof window!=='undefined'&&['localhost','127.0.0.1'].includes(window.location.hostname)){
  return `${window.location.protocol}//${window.location.hostname}:8000/api`;
 }
 return '/api';
}
export async function apiBlob(path:string,body:unknown){
 const token=entraConfigured?await accessToken():'';
 const response=await fetch(`${apiBase()}${path}`,{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify(body)});
 if(!response.ok){const data=await response.json().catch(()=>({detail:'Falha ao gerar relatório'}));throw new Error(data.detail||data.message||'Falha ao gerar relatório')}
 return {blob:await response.blob(),disposition:response.headers.get('content-disposition')||''};
}
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{
 const token=entraConfigured?await accessToken():'';
 const response=await fetch(`${apiBase()}${path}`,{...init,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{}) ,...init.headers}});
 if(!response.ok){const body=await response.json().catch(()=>({message:response.statusText})) as {message?:string;detail?:string|{message?:string}};const detail=typeof body.detail==='string'?body.detail:body.detail?.message;throw Object.assign(new Error(body.message||detail||'Falha na API'),{status:response.status,body})}
 if(response.status===204)return undefined as T;
 return response.json();
}
