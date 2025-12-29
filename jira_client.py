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

        # Handle JWT (Forge/Auto-login) vs Basic Auth (Manual/Local)
        if jwt_token:
            # Forge Remote expects "Bearer"
            self.headers["Authorization"] = f"Bearer {jwt_token}"
            self.auth = None
        elif email and api_token:
            self.auth = HTTPBasicAuth(email, api_token)
        else:
            self.auth = None

    def _request(self, method, url, **kwargs):
        """Central helper to handle auth and headers for all methods."""
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

    # --- AUTH CHECK ---
    def get_myself(self):
        url = f"{self.base_url}/rest/api/3/myself"
        return self._request("GET", url).json()

    # --- ISSUES ---
    def search_issues(self, jql, max_results=100, fields=None):
        url = f"{self.base_url}/rest/api/3/search/jql"
        if not fields:
            fields = ["summary", "project", "issuetype", "assignee", "status", "worklog"]

        payload = {
            "jql": jql,
            "maxResults": int(max_results),
            "fields": fields
        }
        return self._request("POST", url, json=payload).json().get("issues", [])

    def get_my_issues(self, jql=None, max_results=100, fields=None):
        if not jql:
            jql = "assignee = currentUser() ORDER BY updated DESC"
        return self.search_issues(jql, max_results, fields)

    def create_issue(self, project_key, summary, description, issue_type="Task", epic_name=None):
        url = f"{self.base_url}/rest/api/3/issue"
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            },
            "issuetype": {"name": issue_type}
        }
        # Support for Epics
        if issue_type == "Epic" and epic_name:
            fields["customfield_10011"] = epic_name # Update this ID if your Jira uses a different one

        payload = {"fields": fields}
        return self._request("POST", url, json=payload).json()

    # --- PROJECTS ---
    def get_projects(self):
        url = f"{self.base_url}/rest/api/3/project/search"
        return self._request("GET", url).json().get("values", [])

    # --- WORKLOGS ---
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
        max_results = 100
        while True:
            url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
            params = {"startAt": start_at, "maxResults": max_results}
            data = self._request("GET", url, params=params).json()
            worklogs = data.get("worklogs", [])
            all_worklogs.extend(worklogs)
            if start_at + max_results >= data.get("total", 0):
                break
            start_at += max_results
        return all_worklogs

    def update_worklog(self, issue_key, worklog_id, hours, comment):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"
        payload = {
            "timeSpentSeconds": int(hours * 3600),
            "comment": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]
            }
        }
        return self._request("PUT", url, json=payload)

    def delete_worklog(self, issue_key, worklog_id):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"
        return self._request("DELETE", url)
