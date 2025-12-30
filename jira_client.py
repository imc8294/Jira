import requests
from requests.auth import HTTPBasicAuth

class JiraClient:
    def __init__(self, base_url, email=None, api_token=None, jwt_token=None, verify_ssl=True):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Handle JWT vs Basic Auth
        if jwt_token:
            # Forge Bridge mode: Jira expects "JWT <token>"
            self.headers["Authorization"] = f"JWT {jwt_token}"
            self.auth = None
        else:
            # Standalone mode: email + api_token
            self.auth = HTTPBasicAuth(email, api_token) if email and api_token else None

    # -----------------------------
    # Internal request helper (Crucial for clean code)
    # -----------------------------
    def _request(self, method, url, **kwargs):
        """Unified helper to inject headers and auth automatically."""
        kwargs['headers'] = self.headers
        kwargs['verify'] = self.verify_ssl
        if self.auth:
            kwargs['auth'] = self.auth
        
        resp = requests.request(method, url, **kwargs)
        self._raise(resp)
        return resp

    def _raise(self, resp):
        if not resp.ok:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            raise Exception(f"Jira API Error {resp.status_code}: {msg}")

    # -----------------------------
    # API Methods
    # -----------------------------
    def get_myself(self):
        url = f"{self.base_url}/rest/api/3/myself"
        return self._request("GET", url).json()

    def search_issues(self, jql, max_results=100, fields=None):
        url = f"{self.base_url}/rest/api/3/search/jql"
        if not fields:
            fields = ["summary", "project", "issuetype", "assignee", "status"]
        
        payload = {
            "jql": jql,
            "maxResults": int(max_results),
            "fields": fields
        }
        return self._request("POST", url, json=payload).json().get("issues", [])

    def get_my_issues(self, jql=None, max_results=100):
        if not jql:
            jql = "assignee = currentUser() ORDER BY updated DESC"
        return self.search_issues(jql=jql, max_results=max_results)

    def get_projects(self):
        url = f"{self.base_url}/rest/api/3/project/search"
        return self._request("GET", url).json().get("values", [])

    def create_issue(self, project_key, summary, description, issue_type="Task"):
        url = f"{self.base_url}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
                },
                "issuetype": {"name": issue_type}
            }
        }
        return self._request("POST", url, json=payload).json()

    def add_worklog(self, issue_key, time_spent, comment, started):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
        payload = {"timeSpent": time_spent, "started": started}
        if comment:
            payload["comment"] = {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]
            }
        return self._request("POST", url, json=payload).json()

    def get_worklogs(self, issue_key):
        all_worklogs = []
        start_at = 0
        while True:
            url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
            params = {"startAt": start_at, "maxResults": 100}
            data = self._request("GET", url, params=params).json()
            worklogs = data.get("worklogs", [])
            all_worklogs.extend(worklogs)
            if start_at + 100 >= data.get("total", 0): break
            start_at += 100
        return all_worklogs
