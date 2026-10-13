from datetime import datetime, timezone
import httpx
from .config import get_settings

class GraphClient:
    def __init__(self): self.s=get_settings(); self.base="https://graph.microsoft.com/v1.0"
    async def token(self):
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(f"https://login.microsoftonline.com/{self.s.entra_tenant_id}/oauth2/v2.0/token",data={"client_id":self.s.graph_client_id,"client_secret":self.s.graph_client_secret,"scope":"https://graph.microsoft.com/.default","grant_type":"client_credentials"});r.raise_for_status();return r.json()["access_token"]
    async def request(self,method,path,**kwargs):
        headers=kwargs.pop("headers",{});headers["Authorization"]=f"Bearer {await self.token()}"
        async with httpx.AsyncClient(timeout=90,follow_redirects=True) as c:
            r=await c.request(method,self.base+path,headers=headers,**kwargs);r.raise_for_status();return r
    def item_path(self):
        if self.s.sharepoint_excel_item_id:return f"/drives/{self.s.sharepoint_drive_id}/items/{self.s.sharepoint_excel_item_id}"
        return f"/drives/{self.s.sharepoint_drive_id}/root:/{self.s.sharepoint_excel_path}"
    async def metadata(self): return (await self.request("GET",self.item_path())).json()
    async def download_excel(self): return (await self.request("GET",self.item_path()+"/content")).content
    async def upload_excel(self,content:bytes,etag:str|None):
        headers={"Content-Type":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        if etag:headers["If-Match"]=etag
        return (await self.request("PUT",self.item_path()+"/content",content=content,headers=headers)).json()
    async def versions(self): return (await self.request("GET",self.item_path()+"/versions")).json().get("value",[])
    async def backup(self):
        meta=await self.metadata(); stamp=datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        body={"parentReference":{"driveId":self.s.sharepoint_drive_id,"id":self.s.sharepoint_backup_folder_id},"name":f"Panorama_Restricoes_{stamp}.xlsx"}
        return await self.request("POST",f"/drives/{self.s.sharepoint_drive_id}/items/{meta['id']}/copy",json=body)
    async def list_items(self):
        return (await self.request("GET",f"/sites/{self.s.sharepoint_hostname}:{self.s.sharepoint_site_path}:/lists/{self.s.sharepoint_list_id}/items?$expand=fields")).json().get("value",[])

