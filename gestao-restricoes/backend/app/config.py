from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_origin: str = "http://localhost:3000"
    database_url: str = "sqlite+aiosqlite:///./lean_control.db"
    entra_tenant_id: str = ""
    entra_api_client_id: str = ""
    entra_admin_group_id: str = ""
    entra_editor_group_id: str = ""
    entra_viewer_group_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    sharepoint_hostname: str = ""
    sharepoint_site_path: str = ""
    sharepoint_drive_id: str = ""
    sharepoint_excel_item_id: str = ""
    sharepoint_excel_path: str = ""
    sharepoint_backup_folder_id: str = ""
    sharepoint_list_id: str = ""
    sync_provider: str = "excel"
    local_excel_path: str = ""
    local_backup_path: str = ""
    sync_retry_seconds: int = 60
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
