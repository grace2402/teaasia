import requests

class ConfluenceClient:
    def __init__(self, app=None):
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        cfg = app.config["CONFLUENCE"]
        self.base_url  = cfg["BASE_URL"].rstrip("/")
        self.auth      = (cfg["EMAIL"], cfg["API_TOKEN"])
        self.space_key = cfg["SPACE_KEY"]
        self.default_parent = cfg.get("PARENT_ID")

    def create_page(self, title, html_body, parent_id=None):
        """
        在 Confluence 建立一個頁面。
        :param title: 頁面標題
        :param html_body: Storage 格式 HTML 內容
        :param parent_id: 如果要放在某個父頁下，就帶 pageId；不帶就是在 SPACE 根目錄下
        :return: 新頁面的 JSON 回應
        """
        url = f"{self.base_url}/rest/api/content"
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": self.space_key},
            "body": {
                "storage": {
                    "value": html_body,
                    "representation": "storage"
                }
            }
        }
        # 加上 ancestors
        pid = parent_id or self.default_parent
        if pid:
            payload["ancestors"] = [{"id": str(pid)}]

        resp = requests.post(
            url,
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        # 若非 2xx，拋例外讓呼叫方知道
        resp.raise_for_status()
        return resp.json()
    

    def get_child_pages(self, parent_id, limit=50):
        """
        取 parent_id 底下的子頁面列表
        回傳 list of page dicts
        """
        url = f"{self.base_url}/rest/api/content/{parent_id}/child/page?limit={limit}"
        resp = requests.get(url, auth=self.auth, timeout=10)
        resp.raise_for_status()
        return resp.json().get("results", [])
    
    def delete_page(self, page_id):
        """
        刪除 Confluence 上的 page（page_id）。
        """
        url = f"{self.base_url}/rest/api/content/{page_id}"
        resp = requests.delete(
            url,
            auth=self.auth,
            timeout=10
        )
        resp.raise_for_status()
        return resp.status_code  # 204 表示成功