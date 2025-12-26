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
            # If JWT is provided (Auto-login), set the header
            self.headers["Authorization"] = f"JWT {jwt_token}"
            self.auth = None
        else:
            # Otherwise use Basic Auth (Manual login)
            self.auth = HTTPBasicAuth(email, api_token)
 
    # -----------------------------
    # Internal request helper
    # -----------------------------
    def _request(self, method, url, **kwargs):
        """Internal helper to handle auth logic for all methods."""
        kwargs['headers'] = self.headers
        kwargs['verify'] = self.verify_ssl
        if self.auth:
            kwargs['auth'] = self.auth
       
        resp = requests.request(method, url, **kwargs)
        self._raise(resp)
        return resp
 
    # -----------------------------
    # Internal error handler
    # -----------------------------
    def _raise(self, resp):
        if not resp.ok:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            raise Exception(
                f"Jira API Error {resp.status_code}: {msg}"
            )
 
    # -----------------------------
    # Auth check
    # -----------------------------
    def get_myself(self):
        url = f"{self.base_url}/rest/api/3/myself"
        resp = self._request("GET", url)
        return resp.json()
 
    # -----------------------------
    # Generic issue search
    # -----------------------------
    def search_issues(self, jql, max_results=100, fields=None):
        url = f"{self.base_url}/rest/api/3/search/jql"
 
        if not fields:
            fields = ["summary", "project", "issuetype"]
 
        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields
        }
 
        resp = self._request("POST", url, json=payload)
        return resp.json().get("issues", [])
 
    # -----------------------------
    # My assigned issues
    # -----------------------------
    def get_my_issues(self, jql=None, max_results=100, fields=None):
        if not jql:
            jql = "assignee = currentUser() ORDER BY updated DESC"
 
        return self.search_issues(
            jql=jql,
            max_results=max_results,
            fields=fields
        )
 
    # -----------------------------
    # Get all projects
    # -----------------------------
    def get_projects(self):
        url = f"{self.base_url}/rest/api/3/project/search"
        resp = self._request("GET", url)
        return resp.json().get("values", [])
 
    # -----------------------------
    # Create issue
    # -----------------------------
    def create_issue(self, project_key, summary, description, issue_type, epic_name=None):
        url = f"{self.base_url}/rest/api/3/issue"
 
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description}
                        ]
                    }
                ]
            }
        }
 
        if issue_type == "Epic":
            fields["customfield_10011"] = epic_name
 
        payload = {"fields": fields}
        resp = self._request("POST", url, json=payload)
        return resp.json()
 
    # -----------------------------
    # Add worklog
    # -----------------------------
    def add_worklog(self, issue_key, time_spent, comment, started):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
 
        payload = {
            "timeSpent": time_spent,
            "started": started
        }
 
        if comment:
            payload["comment"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": comment}
                        ]
                    }
                ]
            }
 
        resp = self._request("POST", url, json=payload)
        return resp.json()
 
    # -----------------------------
    # Get worklogs (paginated)
    # -----------------------------
    def get_worklogs(self, issue_key):
        all_worklogs = []
        start_at = 0
        max_results = 100
 
        while True:
            url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
            params = {
                "startAt": start_at,
                "maxResults": max_results
            }
 
            resp = self._request("GET", url, params=params)
            data = resp.json()
            worklogs = data.get("worklogs", [])
            all_worklogs.extend(worklogs)
 
            if start_at + max_results >= data.get("total", 0):
                break
 
            start_at += max_results
 
        return all_worklogs
 
    # -----------------------------
    # Update worklog
    # -----------------------------
    def update_worklog(self, issue_key, worklog_id, hours, comment):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"
 
        payload = {
            "timeSpentSeconds": int(hours * 3600),
            "comment": {
                "type": "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment}]
                }]
            }
        }
 
        self._request("PUT", url, json=payload)
 
    # -----------------------------
    # Delete worklog
    # -----------------------------
    def delete_worklog(self, issue_key, worklog_id):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"
        self._request("DELETE", url)
 
    # -----------------------------
    # User Properties & ID
    # -----------------------------
    def get_my_account_id(self):
        me = self.get_myself()
        return me["accountId"]
 
    def set_user_property(self, user_account_id, key, value):
        url = f"{self.base_url}/rest/api/3/user/properties/{key}"
        params = {"accountId": user_account_id}
        payload = value
        self._request("PUT", url, json=payload, params=params)
 
    def get_user_property(self, user_account_id, key):
        url = f"{self.base_url}/rest/api/3/user/properties/{key}"
        params = {"accountId": user_account_id}
 
        # Special handling for 404 in property lookup
        try:
            r = self._request("GET", url, params=params)
            return r.json().get("value")
        except Exception as e:
            if "404" in str(e):
                return None
            raise e
 